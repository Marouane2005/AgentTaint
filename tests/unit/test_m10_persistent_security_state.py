"""M10: durable nonce/confirmation stores + atomic consume + registry probe."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from agenttaint_agent_sdk.confirmation import ConfirmationError, ConfirmationService
from agenttaint_agent_sdk.persistence import (
    DurableConfirmationService,
    DurableNonceStore,
)
from agenttaint_core.schemas import RiskTier
from agenttaint_mcp_proxy.registry_health import probe_registry_available
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_provenance.store import ProvenanceStore
from agenttaint_provenance.trust import load_trust_registry

ROOT = Path(__file__).resolve().parents[2]
SECRET = "m10-test-secret"


def test_durable_nonce_survives_new_store_instance(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'nonces.db'}"
    a = DurableNonceStore(url)
    assert a.try_remember("n1") is True
    b = DurableNonceStore(url)
    assert b.seen("n1") is True
    assert b.try_remember("n1") is False


def test_durable_confirmation_atomic_single_use(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'confirm.db'}"
    svc = DurableConfirmationService(secret=SECRET, database_url=url)
    args = {"to": "bob@corp.example", "body": "hi"}
    rec = svc.request(
        tool="email.send",
        arguments=args,
        agent_id="agent_a",
        risk_tier=RiskTier.HIGH,
        explanation="test",
        provenance_context_hash="ctx-1",
    )
    approved = svc.approve(rec.confirmation_id)
    assert approved.approval_token

    winners: list[str] = []
    errors: list[str] = []

    def worker() -> None:
        try:
            DurableConfirmationService(secret=SECRET, database_url=url).consume(
                confirmation_id=rec.confirmation_id,
                tool="email.send",
                arguments=args,
                agent_id="agent_a",
                approval_token=approved.approval_token,
                provenance_context_hash="ctx-1",
            )
            winners.append("ok")
        except ConfirmationError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(winners) == 1
    assert len(errors) == 7


def test_confirmation_bound_to_provenance_context() -> None:
    svc = ConfirmationService(secret=SECRET)
    args = {"path": "/workspace/a"}
    rec = svc.request(
        tool="filesystem.write",
        arguments=args,
        agent_id="a",
        risk_tier=RiskTier.HIGH,
        explanation="x",
        provenance_context_hash="hash-a",
    )
    approved = svc.approve(rec.confirmation_id)
    with pytest.raises(ConfirmationError, match="provenance context"):
        svc.consume(
            confirmation_id=rec.confirmation_id,
            tool="filesystem.write",
            arguments=args,
            agent_id="a",
            approval_token=approved.approval_token,
            provenance_context_hash="hash-b",
        )


def test_registry_probe_true_and_false() -> None:
    trust = load_trust_registry(ROOT / "policies" / "trust_registry.yaml")
    reg = ProvenanceRegistry(store=ProvenanceStore(), trust=trust)
    assert probe_registry_available(reg) is True

    class Broken:
        def session(self):
            raise RuntimeError("db down")

    class BrokenReg:
        store = Broken()

    assert probe_registry_available(BrokenReg()) is False
