"""Durable nonce and confirmation stores (SQLite by default; Postgres-compatible URLs).

Atomic single-use consume uses conditional UPDATE so concurrent consumers cannot both win.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from agenttaint_core.crypto import generate_nonce, hmac_sign, hmac_verify
from agenttaint_core.schemas import RiskTier
from sqlalchemy import (
    DateTime,
    String,
    Text,
    create_engine,
    select,
    text,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from agenttaint_agent_sdk.confirmation import (
    ConfirmationError,
    ConfirmationRecord,
    ConfirmationStatus,
    arguments_hash,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_engine(database_url: str) -> Any:
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {"future": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


class SecurityStateBase(DeclarativeBase):
    pass


class NonceRow(SecurityStateBase):
    __tablename__ = "envelope_nonces"

    nonce: Mapped[str] = mapped_column(String(128), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConfirmationRow(SecurityStateBase):
    __tablename__ = "confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_redacted_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DurableNonceStore:
    """Persistent nonce replay cache shared across processes via SQLite/Postgres."""

    def __init__(self, database_url: str = "sqlite+pysqlite:///:memory:") -> None:
        self.database_url = database_url
        self.engine = _make_engine(database_url)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        SecurityStateBase.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def seen(self, nonce: str) -> bool:
        with self.session() as session:
            return session.get(NonceRow, nonce) is not None

    def remember(self, nonce: str, *, when: datetime | None = None) -> None:
        """Insert nonce; raise if already present (fail closed on replay)."""
        if not self.try_remember(nonce, when=when):
            raise ValueError("replayed envelope nonce")

    def try_remember(self, nonce: str, *, when: datetime | None = None) -> bool:
        """Atomically claim a nonce. Returns False if already seen."""
        stamp = when or _utcnow()
        with self.session() as session:
            if session.get(NonceRow, nonce) is not None:
                return False
            session.add(NonceRow(nonce=nonce, seen_at=stamp))
            try:
                session.commit()
            except Exception:  # noqa: BLE001 - unique race → already seen
                session.rollback()
                return False
            return True

    def prune(self, older_than: timedelta) -> int:
        cutoff = _utcnow() - older_than
        with self.session() as session:
            rows = session.scalars(select(NonceRow).where(NonceRow.seen_at < cutoff)).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count


class DurableConfirmationService:
    """Persistent confirmation binder with atomic APPROVED → CONSUMED transitions."""

    def __init__(
        self,
        *,
        secret: str,
        database_url: str = "sqlite+pysqlite:///:memory:",
        default_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self.secret = secret
        self.default_ttl = default_ttl
        self.database_url = database_url
        self.engine = _make_engine(database_url)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        SecurityStateBase.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def request(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        agent_id: str,
        risk_tier: RiskTier,
        explanation: str,
        arguments_redacted: dict[str, Any] | None = None,
        policy_id: str | None = None,
        ttl: timedelta | None = None,
        provenance_context_hash: str | None = None,
    ) -> ConfirmationRecord:
        now = _utcnow()
        record = ConfirmationRecord(
            confirmation_id=str(uuid4()),
            tool=tool,
            arguments_hash=arguments_hash(arguments),
            arguments_redacted=dict(arguments_redacted or {}),
            agent_id=agent_id,
            risk_tier=risk_tier,
            explanation=explanation,
            created_at=now,
            expires_at=now + (ttl or self.default_ttl),
            status=ConfirmationStatus.PENDING,
            nonce=generate_nonce(),
            policy_id=policy_id,
            provenance_context_hash=provenance_context_hash,
        )
        with self.session() as session:
            session.add(self._to_row(record))
            session.commit()
        return record

    def approve(self, confirmation_id: str) -> ConfirmationRecord:
        with self.session() as session:
            row = session.get(ConfirmationRow, confirmation_id)
            if row is None:
                raise ConfirmationError("unknown confirmation_id")
            record = self._from_row(row)
            self._ensure_pending_fresh(record)
            record.status = ConfirmationStatus.APPROVED
            record.approval_token = hmac_sign(self.secret, self._token_payload(record))
            row.status = record.status.value
            row.approval_token = record.approval_token
            session.commit()
            return record

    def deny(self, confirmation_id: str) -> ConfirmationRecord:
        with self.session() as session:
            row = session.get(ConfirmationRow, confirmation_id)
            if row is None:
                raise ConfirmationError("unknown confirmation_id")
            record = self._from_row(row)
            self._ensure_pending_fresh(record)
            record.status = ConfirmationStatus.DENIED
            record.approval_token = None
            row.status = record.status.value
            row.approval_token = None
            session.commit()
            return record

    def consume(
        self,
        *,
        confirmation_id: str,
        tool: str,
        arguments: dict[str, Any],
        agent_id: str,
        approval_token: str | None,
        provenance_context_hash: str | None = None,
    ) -> ConfirmationRecord:
        with self.session() as session:
            row = session.get(ConfirmationRow, confirmation_id)
            if row is None:
                raise ConfirmationError("unknown confirmation_id")
            record = self._from_row(row)
            now = _utcnow()
            if record.expires_at < now:
                row.status = ConfirmationStatus.EXPIRED.value
                session.commit()
                raise ConfirmationError("confirmation expired")
            if record.status == ConfirmationStatus.CONSUMED:
                raise ConfirmationError("confirmation already consumed (replay)")
            if record.status == ConfirmationStatus.DENIED:
                raise ConfirmationError("confirmation was denied")
            if record.status != ConfirmationStatus.APPROVED:
                raise ConfirmationError(f"confirmation not approved ({record.status.value})")
            if record.tool != tool:
                raise ConfirmationError("confirmation tool mismatch")
            if record.agent_id != agent_id:
                raise ConfirmationError("confirmation agent mismatch")
            if record.arguments_hash != arguments_hash(arguments):
                raise ConfirmationError(
                    "confirmation arguments mismatch (possible modification after approval)"
                )
            if record.provenance_context_hash is not None:
                if provenance_context_hash != record.provenance_context_hash:
                    raise ConfirmationError("confirmation provenance context mismatch")
            if not approval_token or not record.approval_token:
                raise ConfirmationError("missing approval token")
            if not hmac_verify(self.secret, self._token_payload(record), approval_token):
                raise ConfirmationError("invalid approval token")
            import hmac as hmac_mod

            if not hmac_mod.compare_digest(record.approval_token, approval_token):
                raise ConfirmationError("approval token mismatch")

            # Atomic single-use: only one concurrent consumer can transition.
            result = session.execute(
                update(ConfirmationRow)
                .where(ConfirmationRow.confirmation_id == confirmation_id)
                .where(ConfirmationRow.status == ConfirmationStatus.APPROVED.value)
                .values(status=ConfirmationStatus.CONSUMED.value)
            )
            rowcount = int(getattr(result, "rowcount", 0) or 0)
            if rowcount != 1:
                session.rollback()
                raise ConfirmationError("confirmation already consumed (replay)")
            session.commit()
            record.status = ConfirmationStatus.CONSUMED
            return record

    def get(self, confirmation_id: str) -> ConfirmationRecord | None:
        with self.session() as session:
            row = session.get(ConfirmationRow, confirmation_id)
            return self._from_row(row) if row else None

    def _token_payload(self, record: ConfirmationRecord) -> str:
        return json.dumps(
            {
                "confirmation_id": record.confirmation_id,
                "tool": record.tool,
                "arguments_hash": record.arguments_hash,
                "agent_id": record.agent_id,
                "nonce": record.nonce,
                "expires_at": record.expires_at.astimezone(UTC).isoformat(),
                "provenance_context_hash": record.provenance_context_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _ensure_pending_fresh(self, record: ConfirmationRecord) -> None:
        if record.expires_at < _utcnow():
            record.status = ConfirmationStatus.EXPIRED
            raise ConfirmationError("confirmation expired")
        if record.status != ConfirmationStatus.PENDING:
            raise ConfirmationError(f"confirmation not pending ({record.status.value})")

    @staticmethod
    def _to_row(record: ConfirmationRecord) -> ConfirmationRow:
        return ConfirmationRow(
            confirmation_id=record.confirmation_id,
            tool=record.tool,
            arguments_hash=record.arguments_hash,
            arguments_redacted_json=json.dumps(
                record.arguments_redacted, sort_keys=True, default=str
            ),
            agent_id=record.agent_id,
            risk_tier=record.risk_tier.value,
            explanation=record.explanation,
            created_at=record.created_at,
            expires_at=record.expires_at,
            status=record.status.value,
            nonce=record.nonce,
            approval_token=record.approval_token,
            policy_id=record.policy_id,
            provenance_context_hash=record.provenance_context_hash,
        )

    @staticmethod
    def _from_row(row: ConfirmationRow) -> ConfirmationRecord:
        redacted = json.loads(row.arguments_redacted_json or "{}")
        created = row.created_at
        expires = row.expires_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return ConfirmationRecord(
            confirmation_id=row.confirmation_id,
            tool=row.tool,
            arguments_hash=row.arguments_hash,
            arguments_redacted=dict(redacted),
            agent_id=row.agent_id,
            risk_tier=RiskTier(row.risk_tier),
            explanation=row.explanation,
            created_at=created,
            expires_at=expires,
            status=ConfirmationStatus(row.status),
            nonce=row.nonce,
            approval_token=row.approval_token,
            policy_id=row.policy_id,
            provenance_context_hash=row.provenance_context_hash,
        )


def ping_database(database_url: str) -> bool:
    """Return True if a trivial query succeeds against the database URL."""
    try:
        engine = _make_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - availability probe
        return False
