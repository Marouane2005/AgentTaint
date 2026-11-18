"""FastAPI control plane for the AgentTaint dashboard."""

from __future__ import annotations

import hmac
import os
import re
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agenttaint_api.state import (
    clear_session,
    export_graph,
    get_state,
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


def _require_local_token(x_agenttaint_token: str | None) -> None:
    """Optional shared secret for mutating endpoints (local-trust by default)."""
    expected = os.environ.get("AGENTTAINT_DASHBOARD_TOKEN", "").strip()
    if not expected:
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
    version="0.1.0",
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-AgentTaint-Token"],
)


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
    status = "ok" if registry_ok and audit_ok else "degraded"
    return {
        "status": status,
        "registry_ok": registry_ok,
        "audit_ok": audit_ok,
        "session_mode": state.session.mode,
    }


@app.get("/api/v1/metrics/overview")
def metrics_overview() -> dict[str, Any]:
    return get_state().overview()


@app.get("/api/v1/decisions")
def list_decisions(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    state = get_state()
    rows = state.audit.list_decisions(limit=limit)
    return {
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
            "notes": list(state.session.notes),
        },
        "items": [d.model_dump(mode="json") for d in rows],
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
    _require_local_token(x_agenttaint_token)
    return seed_demo_session()


@app.post("/api/v1/session/clear")
def session_clear(
    x_agenttaint_token: str | None = Header(default=None, alias="X-AgentTaint-Token"),
) -> dict[str, Any]:
    """Reset in-memory demo/live session stores without touching benchmark files."""
    _require_local_token(x_agenttaint_token)
    state = clear_session()
    return {
        "ok": True,
        "session": {
            "mode": state.session.mode,
            "label": state.session.label,
        },
        "overview": state.overview(),
    }
