"""Dashboard API uses real stores — no fabricated decisions."""

from __future__ import annotations

import os
from typing import Any

from agenttaint_api.app import app
from agenttaint_api.state import reset_state_for_tests
from fastapi.testclient import TestClient


def test_health_and_empty_overview() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    overview = client.get("/api/v1/metrics/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["session"]["mode"] == "empty"
    assert body["decisions"]["total"] == 0


def test_demo_seed_produces_real_decisions_and_graph() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    seeded = client.post("/api/v1/demo/seed")
    assert seeded.status_code == 200
    payload = seeded.json()
    assert payload["session"]["mode"] == "demo_seed"
    assert "SIMULATED SCENARIO" in " ".join(payload["session"]["notes"])
    decisions = payload["overview"]["decisions"]
    assert decisions["total"] >= 2
    assert decisions["ALLOW"] >= 1
    assert decisions["BLOCK"] + decisions["CONFIRM"] >= 1

    graph = client.get("/api/v1/graph/export").json()
    assert len(graph["nodes"]) >= 3
    assert "INFERRED" in graph["status_legend"]
    for node in graph["nodes"]:
        assert "metadata" in node
        assert node["metadata"] == {}
        if node.get("content_redacted"):
            assert len(str(node["content_redacted"])) <= 281

    recon = client.get("/api/v1/reconstruction").json()
    assert "not verified causation" in recon["disclaimer"].lower()

    audit = client.get("/api/v1/decisions").json()
    assert len(audit["items"]) >= 2
    assert "arguments_hash" in audit["items"][0]


def test_benchmarks_endpoint_reads_disk_or_empty() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    body = client.get("/api/v1/benchmarks").json()
    assert "disclaimer" in body
    assert "synthetic" in body["disclaimer"].lower()
    if body["available"]:
        assert body["reports"]
        assert "per_defense" in body["reports"][0]
    else:
        assert "make benchmark" in (body["message"] or "").lower()


def test_session_clear_resets_decisions() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    client.post("/api/v1/demo/seed")
    assert client.get("/api/v1/metrics/overview").json()["decisions"]["total"] >= 2
    cleared = client.post("/api/v1/session/clear")
    assert cleared.status_code == 200
    assert cleared.json()["overview"]["decisions"]["total"] == 0


def test_decisions_filter_sort_and_page() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    client.post("/api/v1/demo/seed")
    blocked = client.get("/api/v1/decisions", params={"decision": "BLOCK", "limit": 5})
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["total"] >= 1
    assert body["items"]
    assert all(item["decision"] == "BLOCK" for item in body["items"])
    assert body["limit"] == 5
    page = client.get("/api/v1/decisions", params={"limit": 1, "offset": 0, "sort": "tool"})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] >= 2
    assert client.get("/api/v1/decisions", params={"decision": "MAYBE"}).status_code == 400
    assert client.get("/api/v1/decisions", params={"sort": "secret"}).status_code == 400


def test_health_reports_policy_engine() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    body = client.get("/api/v1/health").json()
    assert body["policy_ok"] is True
    assert body["registry_ok"] is True
    assert body["audit_ok"] is True


def test_decisions_limit_clamped_and_ids_validated() -> None:
    reset_state_for_tests()
    client = TestClient(app)
    assert client.get("/api/v1/decisions?limit=0").status_code == 422
    assert client.get("/api/v1/decisions?limit=9999").status_code == 422
    assert client.get("/api/v1/decisions/bad%20id!").status_code == 400
    assert client.get("/api/v1/spans/@@@").status_code == 400


def test_dashboard_token_guards_mutations(monkeypatch: Any) -> None:
    reset_state_for_tests()
    client = TestClient(app)
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "test-secret")
    try:
        denied = client.post("/api/v1/demo/seed")
        assert denied.status_code == 401
        ok = client.post(
            "/api/v1/demo/seed",
            headers={"X-AgentTaint-Token": "test-secret"},
        )
        assert ok.status_code == 200
        assert client.post("/api/v1/session/clear").status_code == 401
        assert (
            client.post(
                "/api/v1/session/clear",
                headers={"X-AgentTaint-Token": "test-secret"},
            ).status_code
            == 200
        )
    finally:
        monkeypatch.delenv("AGENTTAINT_DASHBOARD_TOKEN", raising=False)
        os.environ.pop("AGENTTAINT_DASHBOARD_TOKEN", None)
