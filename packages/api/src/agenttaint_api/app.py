"""FastAPI control plane for the AgentTaint dashboard."""

from __future__ import annotations

import hmac
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from agenttaint_api import demo as demo_mod
from agenttaint_api.ratelimit import SlidingWindowLimiter, client_address, rule_for
from agenttaint_api.site import router as site_router
from agenttaint_api.site import site_enabled
from agenttaint_api.state import (
    clear_session,
    export_graph,
    get_state,
    live_database_url,
    load_benchmark_summary,
    seed_demo_session,
)

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_DEFAULT_ORIGINS = (
    "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:3001,http://localhost:3001"
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("AGENTTAINT_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def _auth_mode() -> str:
    """Return off | mutations | required.

    - off: no token checks (local demo default when no token configured)
    - mutations: token required for POST (legacy)
    - required: token required for every route except /api/v1/health
    """
    explicit = os.environ.get("AGENTTAINT_API_AUTH", "").strip().lower()
    if explicit in {"off", "mutations", "required"}:
        return explicit
    if os.environ.get("AGENTTAINT_DASHBOARD_TOKEN", "").strip():
        return "required"
    return "off"


def _require_local_token(x_agenttaint_token: str | None) -> None:
    """Enforce dashboard token according to AGENTTAINT_API_AUTH."""
    mode = _auth_mode()
    if mode == "off":
        return
    expected = os.environ.get("AGENTTAINT_DASHBOARD_TOKEN", "").strip()
    if not expected:
        if mode == "required":
            raise HTTPException(
                status_code=503,
                detail="AGENTTAINT_DASHBOARD_TOKEN must be set when API auth is required",
            )
        return
    provided = x_agenttaint_token or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing dashboard token")


def _validate_id(value: str, label: str) -> str:
    if not _ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {label}")
    return value


app = FastAPI(
    title="AgentTaint Control Plane",
    version="1.0.0",
    description=(
        "Read-only + demo-seed API over real provenance/audit stores. "
        "Does not bypass the MCP SecurityGateway. Local-trust by default; "
        "set AGENTTAINT_DASHBOARD_TOKEN to require a shared secret on mutations."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Content-Type",
        "X-AgentTaint-Token",
        "X-AgentTaint-Approver",
        "X-AgentTaint-Admin",
    ],
)

LIMITER = SlidingWindowLimiter()


def _rate_limit_enabled() -> bool:
    flag = os.environ.get("AGENTTAINT_RATE_LIMIT", "").strip().lower()
    if flag in {"0", "off", "false"}:
        return False
    return demo_mod.demo_mode() or flag in {"1", "on", "true"}


@app.middleware("http")
async def rate_limit(request: Request, call_next):  # type: ignore[no-untyped-def]
    if _rate_limit_enabled():
        rule = rule_for(request.method.upper(), request.url.path)
        if rule is not None:
            wait = LIMITER.check(rule, client_address(request))
            if wait > 0:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": str(max(1, int(wait) + 1))},
                )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.middleware("http")
async def enforce_api_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
    """When auth mode is required, gate every route except health."""
    path = request.url.path
    # Only the API is gated: the bundled static UI is public and asks for the
    # token itself (it holds no data until the API answers).
    if not path.startswith("/api/") or path == "/api/v1/health":
        return await call_next(request)
    mode = _auth_mode()
    needs_auth = mode == "required" or (
        mode == "mutations" and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    )
    if needs_auth:
        try:
            _require_local_token(request.headers.get("x-agenttaint-token"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


def _policy_engine_ok() -> bool:
    """True when the Cedar policy text loads and validates. No decision is made."""
    try:
        from agenttaint_policy.cedar_engine import CedarProvenancePolicy

        CedarProvenancePolicy(denylist_tools=set())
    except Exception:  # noqa: BLE001 - health probe must not raise
        return False
    return True


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    state = get_state()
    registry_ok = False
    audit_ok = False
    try:
        state.registry.store.list_spans()
        registry_ok = True
    except Exception:  # noqa: BLE001 - health probe
        registry_ok = False
    try:
        state.audit.list_decisions(limit=1)
        audit_ok = True
    except Exception:  # noqa: BLE001 - health probe
        audit_ok = False
    policy_ok = _policy_engine_ok()
    status = "ok" if registry_ok and audit_ok and policy_ok else "degraded"
    return {
        "status": status,
        "registry_ok": registry_ok,
        "audit_ok": audit_ok,
        "policy_ok": policy_ok,
        "session_mode": state.session.mode,
        "auth_mode": _auth_mode(),
        "demo_mode": demo_mod.demo_mode(),
        "site_enabled": site_enabled(),
    }


@app.get("/api/v1/metrics/overview")
def metrics_overview() -> dict[str, Any]:
    return get_state().overview()


_DECISIONS = {"ALLOW", "CONFIRM", "BLOCK"}
_TIERS = {"LOW", "MEDIUM", "HIGH"}
_SORTS = {"created_at", "tool", "decision", "risk_tier"}


@app.get("/api/v1/decisions")
def list_decisions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
    decision: str | None = Query(default=None),
    risk_tier: str | None = Query(default=None),
    tool: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
) -> dict[str, Any]:
    if decision is not None and decision not in _DECISIONS:
        raise HTTPException(status_code=400, detail="invalid decision")
    if risk_tier is not None and risk_tier not in _TIERS:
        raise HTTPException(status_code=400, detail="invalid risk_tier")
    if sort not in _SORTS:
        raise HTTPException(status_code=400, detail="invalid sort")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="invalid order")
    state = get_state()
    rows, total = state.audit.query_decisions(
        limit=limit,
        offset=offset,
        decision=decision,
        risk_tier=risk_tier,
        tool=tool,
        q=q,
        sort=sort,
        order=order,
    )
    return {
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
            "notes": list(state.session.notes),
        },
        "items": [d.model_dump(mode="json") for d in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.get("/api/v1/decisions/{call_id}")
def get_decision(call_id: str) -> dict[str, Any]:
    _validate_id(call_id, "call_id")
    state = get_state()
    decision = state.audit.get(call_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return {
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
        },
        "decision": decision.model_dump(mode="json"),
    }


@app.get("/api/v1/traces")
def list_traces() -> dict[str, Any]:
    """Seeded traces (span and decision ids per scenario) for the trace sidebar."""
    state = get_state()
    return {
        "session": {"mode": state.session.mode, "label": state.session.label},
        "traces": list(state.traces),
    }


@app.get("/api/v1/graph/export")
def graph_export() -> dict[str, Any]:
    return export_graph(get_state())


@app.get("/api/v1/spans/{span_id}")
def get_span(span_id: str) -> dict[str, Any]:
    _validate_id(span_id, "span_id")
    state = get_state()
    span = state.registry.store.get_span(span_id)
    if span is None:
        raise HTTPException(status_code=404, detail="span not found")
    completeness = state.registry.lineage_completeness(span_id)
    conflicts = state.registry.origin_conflicts(span_id)
    return {
        "span": span.model_dump(mode="json"),
        "completeness": completeness.model_dump(mode="json"),
        "conflicts": conflicts.model_dump(mode="json"),
    }


@app.get("/api/v1/spans/{span_id}/ancestors")
def span_ancestors(span_id: str) -> dict[str, Any]:
    _validate_id(span_id, "span_id")
    state = get_state()
    if state.registry.store.get_span(span_id) is None:
        raise HTTPException(status_code=404, detail="span not found")
    ancestors = state.registry.ancestors(span_id)
    return {
        "span_id": span_id,
        "ancestors": [s.model_dump(mode="json") for s in ancestors],
    }


@app.get("/api/v1/reconstruction")
def reconstruction_view() -> dict[str, Any]:
    state = get_state()
    evidence = list(state.last_reconstruction)
    source = "demo_seed_cache"
    if not evidence:
        for decision in state.audit.list_decisions(limit=50):
            if decision.evidence:
                evidence = [e.model_dump(mode="json") for e in decision.evidence]
                source = f"decision:{decision.call_id}"
                break
    return {
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
            "notes": list(state.session.notes),
        },
        "disclaimer": (
            "INFERRED evidence is not verified causation. "
            "Scores are scrutiny signals, not probabilities."
        ),
        "source": source,
        "evidence": evidence,
        "empty": not evidence,
        "message": None
        if evidence
        else "No reconstruction evidence yet. Seed the demo session first.",
    }


@app.get("/api/v1/benchmarks")
def benchmarks() -> dict[str, Any]:
    return load_benchmark_summary()


@app.post("/api/v1/demo/seed")
def demo_seed(
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
) -> dict[str, Any]:
    """Run the labeled demo scenario through the real enforcement path."""
    if _auth_mode() == "mutations":
        _require_local_token(x_agenttaint_token)
    if live_database_url():
        raise HTTPException(
            status_code=409,
            detail="disabled while connected to a live proxy database (AGENTTAINT_DATABASE_URL)",
        )
    return seed_demo_session()


@app.post("/api/v1/session/clear")
def session_clear(
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
) -> dict[str, Any]:
    """Reset in-memory demo/live session stores without touching benchmark files."""
    if demo_mod.demo_mode():
        raise HTTPException(status_code=403, detail="disabled in the public demo")
    if _auth_mode() == "mutations":
        _require_local_token(x_agenttaint_token)
    if live_database_url():
        raise HTTPException(
            status_code=409,
            detail="disabled while connected to a live proxy database (AGENTTAINT_DATABASE_URL)",
        )
    state = clear_session()
    return {
        "ok": True,
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
        },
        "overview": state.overview(),
    }


# --- Out-of-band confirmation approval ----------------------------------------
#
# These routes are the human approval channel. They ALWAYS require the dashboard
# token (independent of AGENTTAINT_API_AUTH) and are disabled when no token or no
# confirmation secret is configured. The MCP proxy exposes no approval tool.


def _require_approval_token(
    x_agenttaint_token: str | None, x_agenttaint_approver: str | None = None
) -> None:
    """Human approval channel.

    Preferred: a dedicated ``AGENTTAINT_APPROVER_TOKEN`` sent as
    ``X-AgentTaint-Approver``. It must differ from the dashboard read token so a
    token baked into the dashboard bundle (``NEXT_PUBLIC_*``) can never approve.
    Fallback (legacy): the dashboard token in either header.
    The public demo never approves anything, whatever headers are sent.
    """
    if demo_mod.demo_mode():
        raise HTTPException(
            status_code=403,
            detail=(
                "Approvals are disabled in the public demo. In a self-hosted deployment a "
                "person approves held calls with a separate approver token or the CLI."
            ),
        )
    approver = os.environ.get("AGENTTAINT_APPROVER_TOKEN", "").strip()
    dashboard = os.environ.get("AGENTTAINT_DASHBOARD_TOKEN", "").strip()
    if approver:
        if dashboard and hmac.compare_digest(approver, dashboard):
            raise HTTPException(
                status_code=503,
                detail="AGENTTAINT_APPROVER_TOKEN must differ from AGENTTAINT_DASHBOARD_TOKEN",
            )
        if not hmac.compare_digest(x_agenttaint_approver or "", approver):
            raise HTTPException(status_code=401, detail="invalid or missing approver token")
        return
    if not dashboard:
        raise HTTPException(
            status_code=503,
            detail=(
                "confirmation approval disabled: set AGENTTAINT_APPROVER_TOKEN "
                "(or AGENTTAINT_DASHBOARD_TOKEN)"
            ),
        )
    provided = x_agenttaint_approver or x_agenttaint_token or ""
    if not hmac.compare_digest(provided, dashboard):
        raise HTTPException(status_code=401, detail="invalid or missing dashboard token")


def _confirmation_service() -> Any:
    from agenttaint_agent_sdk.persistence import DurableConfirmationService
    from agenttaint_core.config import ConfigurationError, resolve_confirm_secret

    url = os.environ.get("AGENTTAINT_SECURITY_DB_URL", "").strip()
    if not url:
        raise HTTPException(
            status_code=503,
            detail="confirmation approval disabled: set AGENTTAINT_SECURITY_DB_URL",
        )
    try:
        secret = resolve_confirm_secret()
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return DurableConfirmationService(secret=secret, database_url=url)


def _confirmation_view(record: Any) -> dict[str, Any]:
    # Read views never include the approval token; only the approve response does.
    return {
        "confirmation_id": record.confirmation_id,
        "tool": record.tool,
        "agent_id": record.agent_id,
        "risk_tier": record.risk_tier.value,
        "policy_id": record.policy_id,
        "arguments_redacted": record.arguments_redacted,
        "arguments_hash": record.arguments_hash,
        "explanation": record.explanation,
        "status": record.status.value,
        "expires_at": record.expires_at.isoformat(),
    }


@app.get("/api/v1/confirmations")
def list_confirmations(
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
    x_agenttaint_approver: str | None = Header(default=None, alias="X-AgentTaint-Approver"),
) -> dict[str, Any]:
    _require_approval_token(x_agenttaint_token, x_agenttaint_approver)
    service = _confirmation_service()
    return {"pending": [_confirmation_view(r) for r in service.list_by_status()]}


def _decide(confirmation_id: str, approve: bool) -> dict[str, Any]:
    from agenttaint_agent_sdk.confirmation import ConfirmationError

    cid = _validate_id(confirmation_id, "confirmation_id")
    service = _confirmation_service()
    if service.get(cid) is None:
        raise HTTPException(status_code=404, detail="unknown confirmation_id")
    try:
        record = service.approve(cid) if approve else service.deny(cid)
    except ConfirmationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    view = _confirmation_view(record)
    if approve:
        # Returned once, only to the authenticated approver, who relays it to the agent.
        # List/read endpoints never include it.
        view["approval_token"] = record.approval_token
    return view


@app.post("/api/v1/confirmations/{confirmation_id}/approve")
def approve_confirmation(
    confirmation_id: str,
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
    x_agenttaint_approver: str | None = Header(default=None, alias="X-AgentTaint-Approver"),
) -> dict[str, Any]:
    _require_approval_token(x_agenttaint_token, x_agenttaint_approver)
    return _decide(confirmation_id, approve=True)


@app.post("/api/v1/confirmations/{confirmation_id}/deny")
def deny_confirmation(
    confirmation_id: str,
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
    x_agenttaint_approver: str | None = Header(default=None, alias="X-AgentTaint-Approver"),
) -> dict[str, Any]:
    _require_approval_token(x_agenttaint_token, x_agenttaint_approver)
    return _decide(confirmation_id, approve=False)


# --- Demo scenarios ---------------------------------------------------------------


class DemoRun(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=128)


class DemoCustomRun(BaseModel):
    instruction: str = Field(min_length=3, max_length=demo_mod.MAX_INSTRUCTION)
    content: str = Field(default="", max_length=demo_mod.MAX_CONTENT)


@app.get("/api/v1/demo/scenarios")
def demo_scenarios() -> dict[str, Any]:
    """Synthetic scenarios a visitor can replay through the real gateway."""
    try:
        return {"demo_mode": demo_mod.demo_mode(), "scenarios": demo_mod.catalog()}
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="benchmark scenarios not installed") from exc


@app.post("/api/v1/demo/run")
def demo_run(body: DemoRun) -> dict[str, Any]:
    if live_database_url():
        raise HTTPException(
            status_code=409,
            detail="disabled while connected to a live proxy database (AGENTTAINT_DATABASE_URL)",
        )
    _validate_id(body.scenario_id, "scenario_id")
    try:
        return demo_mod.run(body.scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown scenario") from exc


@app.post("/api/v1/demo/custom")
def demo_custom(body: DemoCustomRun) -> dict[str, Any]:
    """Run visitor text through the real gateway; tools are mocks (no shell, no network)."""
    if live_database_url():
        raise HTTPException(
            status_code=409,
            detail="disabled while connected to a live proxy database (AGENTTAINT_DATABASE_URL)",
        )
    try:
        return demo_mod.run_custom(body.instruction, body.content)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="benchmark scenarios not installed") from exc


app.include_router(site_router)


@app.on_event("startup")
def _seed_public_demo() -> None:
    if demo_mod.demo_mode() and not live_database_url():
        demo_mod.seed_if_empty()


@app.get("/", include_in_schema=False, response_model=None)
def root() -> RedirectResponse | JSONResponse:
    """Public demo lands on the product page; self-hosted lands on the console."""
    if demo_mod.demo_mode():
        return RedirectResponse(url="/product/", status_code=307)
    if ui_directory() is not None:
        return RedirectResponse(url="/overview/", status_code=307)
    return JSONResponse({"service": "agenttaint", "docs": "/docs"})


# --- Bundled dashboard UI -------------------------------------------------------
#
# ``npm run build:static`` in apps/dashboard produces a static bundle. When it is
# available (AGENTTAINT_UI_DIR, or shipped inside this package as ``ui/``) the
# control plane serves it at ``/`` so one process and one origin cover API + UI.
# Static files are public; every /api/v1 route keeps its own auth.


def ui_directory() -> Path | None:
    configured = os.environ.get("AGENTTAINT_UI_DIR", "").strip()
    candidate = Path(configured) if configured else Path(__file__).resolve().parent / "ui"
    if (candidate / "index.html").is_file():
        return candidate
    return None


def _mount_ui() -> None:
    from fastapi.staticfiles import StaticFiles

    directory = ui_directory()
    if directory is not None:
        app.mount("/", StaticFiles(directory=directory, html=True), name="ui")


_mount_ui()
