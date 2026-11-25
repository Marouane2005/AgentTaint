"""Write-ahead audit: AuditStore.update upserts the row for an existing call_id."""

from __future__ import annotations

import pytest
from agenttaint_core.schemas import DecisionOutcome, RiskTier, ToolCallDecision

pytest.importorskip("sqlalchemy")
from agenttaint_audit.store import AuditStore  # noqa: E402


def _decision(**kw: object) -> ToolCallDecision:
    base: dict[str, object] = {
        "call_id": "call-1",
        "tool": "email.send",
        "risk_tier": RiskTier.HIGH,
        "arguments_hash": "h",
        "decision": DecisionOutcome.ALLOW,
        "explanation": "ALLOW (forwarding)",
    }
    base.update(kw)
    return ToolCallDecision(**base)  # type: ignore[arg-type]


def test_update_replaces_the_pending_row_instead_of_duplicating_it() -> None:
    store = AuditStore()
    store.record(_decision())
    store.update(_decision(decision=DecisionOutcome.BLOCK, policy_id="backend-error"))
    rows = store.list_decisions()
    assert len(rows) == 1
    assert rows[0].decision == DecisionOutcome.BLOCK and rows[0].policy_id == "backend-error"
    assert store.count_by_decision() == {"BLOCK": 1}


def test_update_inserts_when_no_pending_row_exists() -> None:
    store = AuditStore()
    store.update(_decision(call_id="fresh"))
    assert store.get("fresh") is not None
