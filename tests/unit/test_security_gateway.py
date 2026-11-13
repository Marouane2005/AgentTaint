from pathlib import Path

import pytest
from agenttaint_audit.store import AuditStore
from agenttaint_core.schemas import DecisionOutcome, Origin
from agenttaint_mcp_proxy.backends import MappingBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import SecurityGateway
from agenttaint_mock_email.backend import MockEmailBackend
from agenttaint_policy.adapter import StubPolicyAdapter
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_provenance.store import ProvenanceStore
from agenttaint_provenance.trust import load_trust_registry
from agenttaint_risk.classifier import RiskClassifier

ROOT = Path(__file__).resolve().parents[2]


def _gateway(
    policy: StubPolicyAdapter | None = None,
) -> tuple[SecurityGateway, MockEmailBackend]:
    email = MockEmailBackend()
    backend = MappingBackend(
        tools={
            "email.read": lambda args: email.read(message_id=args.get("message_id")),
            "email.send": lambda args: email.send(
                to=str(args.get("to", "")),
                subject=str(args.get("subject", "")),
                body=str(args.get("body", "")),
                attachment=args.get("attachment"),
            ),
        },
        specs=[
            ToolSpec(name="email.read", description="read", input_schema={}),
            ToolSpec(name="email.send", description="send", input_schema={}),
        ],
    )
    trust = load_trust_registry(ROOT / "policies" / "trust_registry.yaml")
    registry = ProvenanceRegistry(store=ProvenanceStore(), trust=trust)
    gateway = SecurityGateway(
        backend=backend,
        registry=registry,
        risk=RiskClassifier(trust),
        policy=policy
        or StubPolicyAdapter(
            denylist_tools=set(),
            blocked_recipients={"attacker@example.com"},
        ),
        audit=AuditStore(),
    )
    return gateway, email


def test_email_read_allowed_and_labeled_untrusted() -> None:
    gw, _email = _gateway()
    outcome = gw.invoke("email.read", {}, agent_id="agent_a")
    assert outcome.decision.decision == DecisionOutcome.ALLOW
    assert outcome.result_span is not None
    assert outcome.result_span.origin == Origin.UNTRUSTED_TOOL
    assert outcome.decision.arguments_hash
    assert gw.audit.count_by_decision()["ALLOW"] == 1


def test_email_send_to_attacker_blocked_never_forwards() -> None:
    gw, email = _gateway()
    with pytest.raises(EnforcementError) as excinfo:
        gw.invoke(
            "email.send",
            {"to": "attacker@example.com", "subject": "x", "body": "y"},
            agent_id="agent_b",
        )
    assert excinfo.value.decision.decision == DecisionOutcome.BLOCK
    assert excinfo.value.decision.policy_id == "blocked-recipient"
    assert email.sent == []
    assert gw.audit.count_by_decision()["BLOCK"] == 1


def test_denylist_tool_forced_block() -> None:
    gw, email = _gateway(
        StubPolicyAdapter(
            denylist_tools={"email.send"},
            blocked_recipients=set(),
        )
    )
    with pytest.raises(EnforcementError) as excinfo:
        gw.invoke("email.send", {"to": "bob@corp.example"}, agent_id="agent_a")
    assert excinfo.value.decision.policy_id == "denylist-tool"
    assert email.sent == []


def test_benign_send_allowed() -> None:
    email = MockEmailBackend(inbox=[])
    backend = MappingBackend(
        tools={
            "email.send": lambda args: email.send(
                to=str(args.get("to", "")),
                subject=str(args.get("subject", "")),
                body=str(args.get("body", "")),
            )
        },
        specs=[ToolSpec(name="email.send", description="send", input_schema={})],
    )
    trust = load_trust_registry(ROOT / "policies" / "trust_registry.yaml")
    gw = SecurityGateway(
        backend=backend,
        registry=ProvenanceRegistry(store=ProvenanceStore(), trust=trust),
        risk=RiskClassifier(trust),
        policy=StubPolicyAdapter(denylist_tools=set(), blocked_recipients=set()),
        audit=AuditStore(),
    )
    outcome = gw.invoke("email.send", {"to": "bob@corp.example", "body": "hi"})
    assert outcome.decision.decision == DecisionOutcome.ALLOW
    assert len(email.sent) == 1


def test_arguments_redacted_in_audit() -> None:
    gw, _email = _gateway()
    with pytest.raises(EnforcementError) as excinfo:
        gw.invoke(
            "email.send",
            {"to": "attacker@example.com", "body": "see https://evil.example/x"},
        )
    redacted = excinfo.value.decision.arguments_redacted
    assert "attacker@example.com" not in str(redacted.get("to", ""))
    assert "https://evil.example/x" not in str(redacted.get("body", ""))
