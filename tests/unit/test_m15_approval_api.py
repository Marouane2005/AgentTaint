"""M15: control-plane approval endpoints always require the dashboard token."""

from __future__ import annotations

from pathlib import Path

import pytest
from agenttaint_agent_sdk.persistence import DurableConfirmationService
from agenttaint_api.app import app
from agenttaint_core.config import resolve_confirm_secret
from agenttaint_core.schemas import RiskTier
from fastapi.testclient import TestClient


@pytest.fixture()
def pending(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    db = f"sqlite+pysqlite:///{tmp_path / 'sec.db'}"
    monkeypatch.setenv("AGENTTAINT_SECURITY_DB_URL", db)
    monkeypatch.setenv("AGENTTAINT_API_AUTH", "off")
    svc = DurableConfirmationService(secret=resolve_confirm_secret(), database_url=db)
    rec = svc.request(
        tool="email.send",
        arguments={"to": "partner@corp.example"},
        agent_id="agent_a",
        risk_tier=RiskTier.HIGH,
        explanation="x",
    )
    return rec.confirmation_id


def test_approval_disabled_without_dashboard_token(
    monkeypatch: pytest.MonkeyPatch, pending: str
) -> None:
    monkeypatch.delenv("AGENTTAINT_DASHBOARD_TOKEN", raising=False)
    client = TestClient(app)
    assert client.post(f"/api/v1/confirmations/{pending}/approve").status_code == 503
    assert client.get("/api/v1/confirmations").status_code == 503


def test_approval_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch, pending: str) -> None:
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "operator-token-123")
    client = TestClient(app)
    res = client.post(
        f"/api/v1/confirmations/{pending}/approve", headers={"X-AgentTaint-Token": "nope"}
    )
    assert res.status_code == 401


def test_approval_with_token_never_returns_approval_token(
    monkeypatch: pytest.MonkeyPatch, pending: str
) -> None:
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "operator-token-123")
    client = TestClient(app)
    hdr = {"X-AgentTaint-Token": "operator-token-123"}
    listed = client.get("/api/v1/confirmations", headers=hdr).json()
    assert [r["confirmation_id"] for r in listed["pending"]] == [pending]
    res = client.post(f"/api/v1/confirmations/{pending}/approve", headers=hdr)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "APPROVED"
    assert "approval_token" not in body
    again = client.post(f"/api/v1/confirmations/{pending}/approve", headers=hdr)
    assert again.status_code == 409


def test_dedicated_approver_token_required_when_configured(
    monkeypatch: pytest.MonkeyPatch, pending: str
) -> None:
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "read-token-123")
    monkeypatch.setenv("AGENTTAINT_APPROVER_TOKEN", "human-approver-456")
    client = TestClient(app)
    # The dashboard read token (which may be bundled into the UI) cannot approve.
    read_only = {"X-AgentTaint-Token": "read-token-123"}
    assert client.get("/api/v1/confirmations", headers=read_only).status_code == 401
    assert (
        client.post(f"/api/v1/confirmations/{pending}/approve", headers=read_only).status_code
        == 401
    )
    human = {"X-AgentTaint-Token": "read-token-123", "X-AgentTaint-Approver": "human-approver-456"}
    listed = client.get("/api/v1/confirmations", headers=human)
    assert listed.status_code == 200
    res = client.post(f"/api/v1/confirmations/{pending}/deny", headers=human)
    assert res.status_code == 200 and res.json()["status"] == "DENIED"


def test_approver_token_must_differ_from_dashboard_token(
    monkeypatch: pytest.MonkeyPatch, pending: str
) -> None:
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "same-token-789")
    monkeypatch.setenv("AGENTTAINT_APPROVER_TOKEN", "same-token-789")
    client = TestClient(app)
    hdr = {"X-AgentTaint-Token": "same-token-789", "X-AgentTaint-Approver": "same-token-789"}
    assert client.get("/api/v1/confirmations", headers=hdr).status_code == 503


def test_seed_records_traces_and_replays_benchmark_scenarios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTTAINT_API_AUTH", "off")
    monkeypatch.delenv("AGENTTAINT_SECURITY_DB_URL", raising=False)
    client = TestClient(app)
    assert client.post("/api/v1/demo/seed").status_code == 200
    traces = client.get("/api/v1/traces").json()["traces"]
    assert traces[0]["trace_id"] == "demo-email-exfil"
    assert len(traces) > 5
    decisions = client.get("/api/v1/decisions?limit=500").json()["items"]
    call_ids = {d["call_id"] for d in decisions}
    for t in traces:
        assert set(t["call_ids"]) <= call_ids
    kinds = {d["decision"] for d in decisions}
    assert {"ALLOW", "BLOCK", "CONFIRM"} <= kinds
