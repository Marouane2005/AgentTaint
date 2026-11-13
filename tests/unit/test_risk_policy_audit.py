from pathlib import Path

from agenttaint_audit.store import AuditStore
from agenttaint_core.schemas import DecisionOutcome, RiskTier, ToolCallDecision
from agenttaint_policy.adapter import StubPolicyAdapter
from agenttaint_policy.loader import load_stub_policy
from agenttaint_provenance.trust import load_trust_registry
from agenttaint_risk.classifier import RiskClassifier

ROOT = Path(__file__).resolve().parents[2]


def test_risk_email_send_high() -> None:
    trust = load_trust_registry(ROOT / "policies" / "trust_registry.yaml")
    risk = RiskClassifier(trust)
    assert risk.classify("email.send", {"to": "a@b.com"}) == RiskTier.HIGH
    assert risk.classify("email.read", {}) == RiskTier.LOW


def test_stub_policy_denylist_and_blocked_recipient() -> None:
    policy = StubPolicyAdapter(
        denylist_tools={"shell.execute"},
        blocked_recipients={"attacker@example.com"},
    )
    blocked_tool = policy.evaluate(
        tool_name="shell.execute",
        arguments={},
        risk_tier=RiskTier.HIGH,
    )
    assert blocked_tool.decision == DecisionOutcome.BLOCK
    assert blocked_tool.policy_id == "denylist-tool"

    blocked_rcpt = policy.evaluate(
        tool_name="email.send",
        arguments={"to": "Attacker@Example.com"},
        risk_tier=RiskTier.HIGH,
    )
    assert blocked_rcpt.decision == DecisionOutcome.BLOCK
    assert blocked_rcpt.policy_id == "blocked-recipient"

    allowed = policy.evaluate(
        tool_name="email.read",
        arguments={},
        risk_tier=RiskTier.LOW,
    )
    assert allowed.decision == DecisionOutcome.ALLOW


def test_load_stub_policy_yaml() -> None:
    policy = load_stub_policy(ROOT / "policies" / "stub_policy.yaml")
    assert "attacker@example.com" in policy.blocked_recipients


def test_audit_store_roundtrip() -> None:
    store = AuditStore("sqlite+pysqlite:///:memory:")
    decision = ToolCallDecision(
        tool="email.send",
        risk_tier=RiskTier.HIGH,
        arguments_hash="abc",
        arguments_redacted={"to": "[REDACTED_EMAIL]"},
        decision=DecisionOutcome.BLOCK,
        policy_id="blocked-recipient",
        explanation="blocked",
    )
    store.record(decision)
    loaded = store.get(decision.call_id)
    assert loaded is not None
    assert loaded.decision == DecisionOutcome.BLOCK
    assert store.count_by_decision()["BLOCK"] == 1
