"""M11: persistent security state, per-agent keys, auth, fail-closed DB paths."""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from agenttaint_agent_sdk.confirmation import ConfirmationError
from agenttaint_agent_sdk.envelope import EnvelopeError, EnvelopeVerifier
from agenttaint_agent_sdk.keys import AgentKeyring, KeyringError
from agenttaint_agent_sdk.persistence import (
    DurableConfirmationService,
    DurableNonceStore,
)
from agenttaint_core.schemas import RiskTier
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_provenance.store import ProvenanceStore
from agenttaint_provenance.trust import load_trust_registry
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SECRET_A = "agent-a-secret"
SECRET_B = "agent-b-secret"


@pytest.fixture
def registry() -> ProvenanceRegistry:
    trust = load_trust_registry(ROOT / "policies" / "trust_registry.yaml")
    return ProvenanceRegistry(store=ProvenanceStore(), trust=trust)


def test_per_agent_keys_prevent_sender_forgery(registry: ProvenanceRegistry) -> None:
    parent = registry.record_user_instruction(content="hi", agent_id="agent_a")
    keyring = AgentKeyring()
    keyring.add("agent_a", SECRET_A)
    keyring.add("agent_b", SECRET_B)
    verifier = EnvelopeVerifier(
        registry=registry,
        keyring=keyring,
        allowed_agents={"agent_a", "agent_b"},
    )
    env = verifier.create(
        sender_agent="agent_b",
        recipient_agent="agent_a",
        content="payload",
        parent_span_ids=[parent.span_id],
    )
    # Attacker renames sender_agent to agent_a but keeps agent_b's signature.
    forged = env.model_copy(update={"sender_agent": "agent_a"})
    with pytest.raises(EnvelopeError, match="signature"):
        verifier.verify(forged)
    # Legitimate verify still works (fresh nonce store for second check).
    verifier2 = EnvelopeVerifier(
        registry=registry,
        keyring=keyring,
        allowed_agents={"agent_a", "agent_b"},
    )
    env2 = verifier2.create(
        sender_agent="agent_a",
        recipient_agent="agent_b",
        content="payload-2",
        parent_span_ids=[parent.span_id],
    )
    assert verifier2.verify(env2).sender_agent == "agent_a"


def test_unknown_agent_key_fails_closed(registry: ProvenanceRegistry) -> None:
    keyring = AgentKeyring()
    keyring.add("agent_a", SECRET_A)
    with pytest.raises(KeyringError):
        keyring.secret_for("agent_z")
    verifier = EnvelopeVerifier(registry=registry, keyring=keyring)
    parent = registry.record_user_instruction(content="x", agent_id="agent_a")
    with pytest.raises(EnvelopeError):
        verifier.create(
            sender_agent="agent_z",
            recipient_agent="agent_a",
            content="x",
            parent_span_ids=[parent.span_id],
        )


def test_confirmation_expiry_and_restart(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'c.db'}"
    svc = DurableConfirmationService(secret="s", database_url=url)
    args = {"to": "bob@corp.example"}
    rec = svc.request(
        tool="email.send",
        arguments=args,
        agent_id="a",
        risk_tier=RiskTier.HIGH,
        explanation="x",
        ttl=timedelta(milliseconds=1),
        provenance_context_hash="h",
    )
    import time

    time.sleep(0.02)
    with pytest.raises(ConfirmationError, match="expired"):
        svc.approve(rec.confirmation_id)

    # Restart: new process handle, same DB, pending record still visible as expired.
    svc2 = DurableConfirmationService(secret="s", database_url=url)
    again = svc2.get(rec.confirmation_id)
    assert again is not None
    with pytest.raises(ConfirmationError):
        svc2.approve(rec.confirmation_id)


def test_nonce_store_fail_closed_on_bad_path() -> None:
    from sqlalchemy.exc import OperationalError

    with pytest.raises(OperationalError):
        DurableNonceStore("sqlite+pysqlite:////no/such/dir/nonces.db")


def test_api_required_auth_blocks_reads(monkeypatch: Any) -> None:
    from agenttaint_api.app import app
    from agenttaint_api.state import reset_state_for_tests

    reset_state_for_tests()
    monkeypatch.setenv("AGENTTAINT_DASHBOARD_TOKEN", "strict-secret")
    monkeypatch.setenv("AGENTTAINT_API_AUTH", "required")
    client = TestClient(app)
    try:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/metrics/overview").status_code == 401
        ok = client.get(
            "/api/v1/metrics/overview",
            headers={"X-AgentTaint-Token": "strict-secret"},
        )
        assert ok.status_code == 200
    finally:
        monkeypatch.delenv("AGENTTAINT_DASHBOARD_TOKEN", raising=False)
        monkeypatch.delenv("AGENTTAINT_API_AUTH", raising=False)
        os.environ.pop("AGENTTAINT_DASHBOARD_TOKEN", None)
        os.environ.pop("AGENTTAINT_API_AUTH", None)


@pytest.mark.postgres
def test_postgres_security_store_roundtrip() -> None:
    url = os.environ.get("AGENTTAINT_TEST_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("AGENTTAINT_TEST_POSTGRES_URL not set")
    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg not installed")

    nonce = f"pg-nonce-{uuid.uuid4().hex}"  # unique: the database outlives test runs
    nonces = DurableNonceStore(url)
    assert nonces.try_remember(nonce) is True
    assert nonces.try_remember(nonce) is False

    svc = DurableConfirmationService(secret="pg", database_url=url)
    args = {"to": "bob@corp.example"}
    rec = svc.request(
        tool="email.send",
        arguments=args,
        agent_id="a",
        risk_tier=RiskTier.HIGH,
        explanation="pg",
        provenance_context_hash="pg-ctx",
    )
    approved = svc.approve(rec.confirmation_id)
    svc.consume(
        confirmation_id=rec.confirmation_id,
        tool="email.send",
        arguments=args,
        agent_id="a",
        approval_token=approved.approval_token,
        provenance_context_hash="pg-ctx",
    )
    with pytest.raises(ConfirmationError):
        svc.consume(
            confirmation_id=rec.confirmation_id,
            tool="email.send",
            arguments=args,
            agent_id="a",
            approval_token=approved.approval_token,
            provenance_context_hash="pg-ctx",
        )
