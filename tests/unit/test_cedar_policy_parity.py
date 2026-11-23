"""Cedar engine: schema validity, exhaustive parity with the Python reference, fail-closed."""

from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path

import pytest
from agenttaint_core.schemas import DecisionOutcome, ProvenanceStatus, RiskTier
from agenttaint_policy.adapter import ProvenanceAwarePolicy
from agenttaint_policy.cedar_engine import (
    CedarPolicyError,
    CedarProvenancePolicy,
    policy_ids_in_order,
)
from agenttaint_policy.context import PolicyContext
from agenttaint_policy.grants import AuthorizationGrant
from agenttaint_policy.loader import load_policy

ROOT = Path(__file__).resolve().parents[2]
BLOCKED = "attacker@example.com"
CONFIG_FLAGS = (
    "confirm_untrusted_influence",
    "fail_closed_unknown_high",
    "confirm_medium_untrusted",
    "scrutinize_medium_undeclared",
    "fail_closed_unknown_medium",
)


def _pair(flags: dict[str, bool]) -> tuple[ProvenanceAwarePolicy, CedarProvenancePolicy]:
    ref = ProvenanceAwarePolicy(
        denylist_tools={"shell.execute"}, blocked_recipients={BLOCKED}, **flags
    )
    return ref, CedarProvenancePolicy.from_reference(ref)


def _cases() -> list[tuple[str, dict[str, str], RiskTier, PolicyContext]]:
    cases = []
    tools = [
        ("email.send", {"to": "bob@corp.example", "body": "hi"}),
        ("email.send", {"to": BLOCKED, "body": "hi"}),
        ("shell.execute", {"command": "ls"}),
    ]
    for (tool, args), tier, status, granted, *bits in itertools.product(
        tools,
        list(RiskTier),
        list(ProvenanceStatus),
        [False, True],
        *([[False, True]] * 6),
    ):
        registry, confirmed, untrusted, inferred, declared, seen = bits
        grants = []
        if granted:
            arg = "to" if "to" in args else "command"
            grants = [AuthorizationGrant(tool=tool, argument=arg, value=args[arg])]
        ctx = PolicyContext(
            provenance_status=status,
            has_untrusted_influence=untrusted,
            influence_inferred_only=inferred,
            authorization_grants=grants,
            registry_available=registry,
            confirmation_validated=confirmed,
            lineage_declared=declared,
            session_untrusted_seen=seen,
            agent_id="agent_a",
        )
        cases.append((tool, args, tier, ctx))
    return cases


CASES = _cases()


def test_policies_validate_against_schema_and_all_have_ids() -> None:
    import cedarpy

    root = ROOT / "packages/policy/src/agenttaint_policy/cedar"
    text = (root / "agenttaint.cedar").read_text()
    result = cedarpy.validate_policies(text, (root / "agenttaint.cedarschema.json").read_text())
    assert result.validation_passed, result.errors
    ids = policy_ids_in_order(text)
    assert len(ids) == 20
    assert len(ids) == len(set(ids))
    assert ids[0] == "fail-closed-registry-unavailable"
    assert "allow-high-authorized" in ids
    assert "allow-medium-authorized" in ids
    assert "allow-medium" in ids
    assert "allow-low" in ids


@pytest.mark.parametrize(
    "flag_values",
    list(itertools.product([False, True], repeat=len(CONFIG_FLAGS))),
    ids=lambda v: "".join("1" if b else "0" for b in v),
)
def test_exhaustive_parity_with_python_reference(flag_values: tuple[bool, ...]) -> None:
    ref, cedar = _pair(dict(zip(CONFIG_FLAGS, flag_values, strict=True)))
    mismatches = []
    for tool, args, tier, ctx in CASES:
        a = ref.evaluate(tool_name=tool, arguments=args, risk_tier=tier, context=ctx)
        b = cedar.evaluate(tool_name=tool, arguments=args, risk_tier=tier, context=ctx)
        if (a.decision, a.policy_id) != (b.decision, b.policy_id):
            mismatches.append((tool, args.get("to"), tier, ctx, a.policy_id, b.policy_id))
    assert not mismatches, mismatches[:5]
    assert not any(
        cedar.evaluate(tool_name=t, arguments=a, risk_tier=r, context=c).policy_id
        == "cedar-default-deny"
        for t, a, r, c in CASES[:50]
    )


def test_untrusted_high_risk_blocked_by_cedar() -> None:
    _, cedar = _pair({})
    ctx = PolicyContext(provenance_status=ProvenanceStatus.KNOWN, has_untrusted_influence=True)
    res = cedar.evaluate(
        tool_name="email.send",
        arguments={"to": "x@evil.example"},
        risk_tier=RiskTier.HIGH,
        context=ctx,
    )
    assert res.decision == DecisionOutcome.BLOCK
    assert res.policy_id == "block-untrusted-influence"
    assert res.explanation.startswith("[cedar]")


def test_missing_fact_fails_closed() -> None:
    _, cedar = _pair({})
    facts = cedar.facts(
        tool_name="http.get",
        arguments={"url": "https://a.example"},
        risk_tier=RiskTier.LOW,
        agent_id=None,
        ctx=PolicyContext(),
    )
    del facts["denylisted"]
    decision, policy_id = cedar.decide(facts)
    assert decision == DecisionOutcome.BLOCK
    assert policy_id == "cedar-evaluation-error"


def test_mistyped_fact_fails_closed() -> None:
    _, cedar = _pair({})
    facts = cedar.facts(
        tool_name="http.get",
        arguments={},
        risk_tier=RiskTier.LOW,
        agent_id=None,
        ctx=PolicyContext(),
    )
    facts["denylisted"] = "no"
    assert cedar.decide(facts)[0] == DecisionOutcome.BLOCK


def test_invalid_policy_rejected_at_load() -> None:
    with pytest.raises(CedarPolicyError):
        CedarProvenancePolicy(
            denylist_tools=set(),
            policy_text='@id("x")\npermit (principal, action, resource) when { context.nope };\n',
        )


def test_policy_without_id_rejected() -> None:
    with pytest.raises(CedarPolicyError):
        CedarProvenancePolicy(
            denylist_tools=set(),
            policy_text="permit (principal, action, resource);\n",
        )


def test_loader_defaults_to_cedar_and_python_is_opt_in(tmp_path: Path) -> None:
    default = load_policy(ROOT / "policies" / "provenance_policy.yaml")
    assert isinstance(default, CedarProvenancePolicy)
    assert default.blocked_recipients == {BLOCKED}
    alt = tmp_path / "p.yaml"
    alt.write_text("engine: python\ndenylist_tools: []\n")
    assert isinstance(load_policy(alt), ProvenanceAwarePolicy)
    bad = tmp_path / "bad.yaml"
    bad.write_text("engine: magic\n")
    with pytest.raises(ValueError):
        load_policy(bad)


def test_context_dataclass_unchanged_by_cedar() -> None:
    _, cedar = _pair({})
    ctx = PolicyContext(provenance_status=ProvenanceStatus.INFERRED)
    before = replace(ctx)
    cedar.evaluate(tool_name="email.send", arguments={}, risk_tier=RiskTier.HIGH, context=ctx)
    assert ctx == before
    assert ctx.provenance_status == ProvenanceStatus.INFERRED
