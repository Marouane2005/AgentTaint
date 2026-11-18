"""Product site backend: Pro waitlist signup and a token-protected admin list.

Enabled when ``AGENTTAINT_DEMO_MODE=1`` or ``AGENTTAINT_SITE_DB_URL`` is set.
Emails are stored in ``AGENTTAINT_SITE_DB_URL`` (Postgres in the hosted demo).
Only the email, a timestamp and the signup source are kept: no IP addresses.
The admin list needs ``X-AgentTaint-Admin: $AGENTTAINT_ADMIN_TOKEN``.
"""

from __future__ import annotations

import csv
import hmac
import io
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

MIN_ADMIN_TOKEN = 24
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,190}\.[A-Za-z]{2,24}$")

router = APIRouter()


class _Base(DeclarativeBase):
    pass


class WaitlistEntry(_Base):
    __tablename__ = "agenttaint_waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="pro")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="landing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_ENGINE: Engine | None = None
_ENGINE_LOCK = threading.Lock()


def site_enabled() -> bool:
    from agenttaint_api.demo import demo_mode

    return demo_mode() or bool(os.environ.get("AGENTTAINT_SITE_DB_URL", "").strip())


def normalize_db_url(url: str) -> str:
    """Accept provider URLs (postgres://, postgresql://) and use the psycopg driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def _db_url() -> str:
    configured = os.environ.get("AGENTTAINT_SITE_DB_URL", "").strip()
    if configured:
        return normalize_db_url(configured)
    from agenttaint_api.state import DEFAULT_DATA

    Path(DEFAULT_DATA).mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{Path(DEFAULT_DATA) / 'site.db'}"


def engine() -> Engine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = create_engine(_db_url(), pool_pre_ping=True, future=True)
            _Base.metadata.create_all(_ENGINE)
        return _ENGINE


def reset_engine_for_tests() -> None:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None


class WaitlistSignup(BaseModel):
    email: str = Field(max_length=254)
    source: str = Field(default="landing", max_length=64)
    # Honeypot: real visitors never see or fill this field.
    website: str = Field(default="", max_length=200)


def _require_enabled() -> None:
    if not site_enabled():
        raise HTTPException(status_code=404, detail="not found")


@router.post("/api/v1/waitlist")
def join_waitlist(body: WaitlistSignup) -> dict[str, Any]:
    _require_enabled()
    message = "Thanks. You're on the Pro waitlist; we'll email you when checkout opens."
    if body.website.strip():
        return {"ok": True, "message": message}
    from agenttaint_api.demo import demo_mode

    if demo_mode() and not os.environ.get("AGENTTAINT_SITE_DB_URL", "").strip():
        # The demo host's disk is ephemeral: refuse rather than lose signups.
        raise HTTPException(
            status_code=503,
            detail="The waitlist is not accepting signups yet. Please email us instead.",
        )
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    source = re.sub(r"[^a-z0-9_-]", "", body.source.lower())[:64] or "landing"
    with Session(engine()) as session:
        session.add(WaitlistEntry(email=email, source=source, created_at=datetime.now(UTC)))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()  # already listed: same answer, no enumeration
    return {"ok": True, "message": message}


def _require_admin(token: str | None) -> None:
    expected = os.environ.get("AGENTTAINT_ADMIN_TOKEN", "").strip()
    if len(expected) < MIN_ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="admin view disabled: no admin token set")
    if not hmac.compare_digest((token or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing admin token")


@router.get("/api/v1/admin/waitlist", response_model=None)
def list_waitlist(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    x_agenttaint_admin: str | None = Header(default=None, alias="X-AgentTaint-Admin"),
) -> dict[str, Any] | PlainTextResponse:
    _require_enabled()
    _require_admin(x_agenttaint_admin)
    with Session(engine()) as session:
        rows = session.scalars(select(WaitlistEntry).order_by(WaitlistEntry.created_at)).all()
        entries = [
            {
                "email": r.email,
                "plan": r.plan,
                "source": r.source,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["email", "plan", "source", "created_at"])
        writer.writeheader()
        writer.writerows(entries)
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=agenttaint-waitlist.csv"},
        )
    return {"count": len(entries), "entries": entries}
