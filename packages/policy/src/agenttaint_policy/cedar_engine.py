"""Cedar-backed provenance policy.

The gateway derives deterministic facts about a tool call; Cedar policies in
``agenttaint_policy/cedar/agenttaint.cedar`` (validated against
``agenttaint.cedarschema.json``) make the ALLOW / CONFIRM / BLOCK decision.

The Python ``ProvenanceAwarePolicy`` is kept as the executable reference; an
exhaustive parity test checks that both produce identical decisions and policy
ids for every combination of facts and configuration flags.

Fail-closed behaviour:
- cedarpy missing, policy/schema invalid  -> ``CedarPolicyError`` at load time.
- evaluation errors or no matching policy  -> BLOCK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from agenttaint_core.schemas import DecisionOutcome, ProvenanceStatus, RiskTier

from agenttaint_policy.adapter import PolicyResult, ProvenanceAwarePolicy
from agenttaint_policy.context import PolicyContext
from agenttaint_policy.grants import grants_cover_authority_arguments

ACTION_EXECUTE = 'Action::"execute"'
ACTION_CONFIRM = 'Action::"execute_with_confirmation"'

_POLICY_HEAD = re.compile(r"^\s*(permit|forbid)\s*\(", re.MULTILINE)
_ANNOTATED_HEAD = re.compile(r'@id\("([^"]+)"\)\s*(permit|forbid)\s*\(')

_EXPLANATIONS: dict[str, str] = {
    "fail-closed-registry-unavailable": (
        "High-risk operation blocked: provenance registry unavailable (fail closed)."
    ),
    "denylist-tool": "Tool is on the enforcement denylist.",
    "confirmation-bound-allow": "Bound user confirmation validated for this exact action.",
    "blocked-recipient": "Recipient is blocked by policy.",
    "allow-high-authorized": (
        "Authority arguments are covered by structured session/agent authorization grants."
    ),
    "allow-medium-authorized": (
        "Authority arguments are covered by structured session/agent authorization grants."
    ),
    "allow-user-authorized-authority": (
        "Authority arguments are covered by structured session/agent authorization grants."
    ),
    "confirm-inferred-untrusted-influence": (
        "INFERRED untrusted influence on a high-risk action; requires bound confirmation "
        "(inference is not authorization)."
    ),
    "block-inferred-untrusted-influence": (
        "Blocked: INFERRED untrusted influence cannot authorize high-risk actions."
    ),
    "confirm-untrusted-influence": (
        "Untrusted provenance influenced a high-risk authority or content argument; "
        "confirmation required."
    ),
    "block-untrusted-influence": (
        "Blocked: untrusted information influenced a high-risk action without explicit "
        "structured USER authorization."
    ),
    "block-unknown-high-risk": "High-risk operation blocked: provenance is UNKNOWN/PARTIAL.",
    "confirm-unknown-high-risk": (
        "High-risk operation with UNKNOWN/PARTIAL provenance requires confirmation."
    ),
    "confirm-high-risk": "High-risk operation requires explicit bound confirmation.",
    "confirm-medium-inferred-untrusted": (
        "MEDIUM sink with INFERRED untrusted influence on destination/path/content; "
        "confirmation required."
    ),
    "confirm-medium-untrusted-influence": (
        "MEDIUM sink with untrusted influence on destination, path, or content; "
        "confirmation required."
    ),
    "block-medium-untrusted-influence": (
        "Blocked: untrusted information influenced a MEDIUM sink without structured authorization."
    ),
    "block-medium-undeclared-lineage": (
        "Blocked: MEDIUM sink with undeclared (UNKNOWN) lineage after the session ingested "
        "untrusted content (fail closed)."
    ),
    "confirm-medium-undeclared-lineage": (
        "MEDIUM sink with undeclared (UNKNOWN) lineage after the session ingested untrusted "
        "content; confirmation required."
    ),
    "allow-medium": "Non-high-risk operation allowed under provenance-aware policy.",
    "allow-low": "Non-high-risk operation allowed under provenance-aware policy.",
    "allow-low-medium": "Non-high-risk operation allowed under provenance-aware policy.",
}


class CedarPolicyError(RuntimeError):
    """Cedar engine could not be loaded; callers must not fall back silently."""


def _read_resource(name: str) -> str:
    return resources.files("agenttaint_policy").joinpath("cedar", name).read_text(encoding="utf-8")


def policy_ids_in_order(policy_text: str) -> list[str]:
    """Return the @id of each policy in source order (Cedar names them policy0..N)."""
    annotated = [m.group(1) for m in _ANNOTATED_HEAD.finditer(policy_text)]
    heads = _POLICY_HEAD.findall(policy_text)
    if len(annotated) != len(heads):
        raise CedarPolicyError("every Cedar policy must carry an @id annotation")
    return annotated


@dataclass
class CedarProvenancePolicy:
    """PolicyAdapter whose decisions come from Cedar policies."""

    denylist_tools: set[str]
    confirm_untrusted_influence: bool = False
    fail_closed_unknown_high: bool = False
    blocked_recipients: set[str] | None = None
    confirm_medium_untrusted: bool = True
    scrutinize_medium_undeclared: bool = True
    fail_closed_unknown_medium: bool = False
    policy_text: str = field(default_factory=lambda: _read_resource("agenttaint.cedar"))
    schema_text: str = field(default_factory=lambda: _read_resource("agenttaint.cedarschema.json"))
    engine_name: str = "cedar"

    def __post_init__(self) -> None:
        try:
            import cedarpy
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise CedarPolicyError("cedarpy is required for the Cedar policy engine") from exc
        self._cedar = cedarpy
        result = cedarpy.validate_policies(self.policy_text, self.schema_text)
        if not result.validation_passed:
            raise CedarPolicyError(f"Cedar policies failed schema validation: {result.errors}")
        self._ids = policy_ids_in_order(self.policy_text)
        self._policies = cedarpy.PolicySet.from_str(self.policy_text)
        # Requests are validated against the schema, so a missing or mistyped
        # fact is an evaluation error (-> BLOCK), never a silent default.
        self._schema = cedarpy.Schema.from_json_str(self.schema_text)

    @classmethod
    def from_reference(cls, ref: ProvenanceAwarePolicy) -> CedarProvenancePolicy:
        return cls(
            denylist_tools=set(ref.denylist_tools),
            confirm_untrusted_influence=ref.confirm_untrusted_influence,
            fail_closed_unknown_high=ref.fail_closed_unknown_high,
            blocked_recipients=set(ref.blocked_recipients) if ref.blocked_recipients else None,
            confirm_medium_untrusted=ref.confirm_medium_untrusted,
            scrutinize_medium_undeclared=ref.scrutinize_medium_undeclared,
            fail_closed_unknown_medium=ref.fail_closed_unknown_medium,
        )

    def facts(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None,
        ctx: PolicyContext,
    ) -> dict[str, Any]:
        """Deterministic request context passed to Cedar (also written to tests)."""
        effective_agent = agent_id or ctx.agent_id
        granted = bool(ctx.authorization_grants) and grants_cover_authority_arguments(
            grants=ctx.authorization_grants,
            tool_name=tool_name,
            arguments=arguments,
            authority_argument_names=ctx.authority_argument_names,
            agent_id=effective_agent,
            session_id=ctx.session_id,
        )
        recipient_blocked = False
        if self.blocked_recipients and tool_name == "email.send":
            recipient = str(arguments.get("to", "")).strip().lower()
            recipient_blocked = recipient in self.blocked_recipients
        return {
            "tier": risk_tier.value,
            "provenance_status": ctx.provenance_status.value,
            "registry_available": bool(ctx.registry_available),
            "denylisted": tool_name in self.denylist_tools,
            "confirmation_validated": bool(ctx.confirmation_validated),
            "granted": granted,
            "recipient_blocked": recipient_blocked,
            "untrusted_influence": bool(ctx.has_untrusted_influence),
            "influence_inferred_only": bool(ctx.influence_inferred_only),
            "provenance_unknown_or_partial": ctx.provenance_status
            in {ProvenanceStatus.UNKNOWN, ProvenanceStatus.PARTIAL},
            "lineage_declared": bool(ctx.lineage_declared),
            "session_untrusted_seen": bool(ctx.session_untrusted_seen),
            "cfg_confirm_untrusted_influence": self.confirm_untrusted_influence,
            "cfg_fail_closed_unknown_high": self.fail_closed_unknown_high,
            "cfg_confirm_medium_untrusted": self.confirm_medium_untrusted,
            "cfg_scrutinize_medium_undeclared": self.scrutinize_medium_undeclared,
            "cfg_fail_closed_unknown_medium": self.fail_closed_unknown_medium,
        }

    def _authorize(self, action: str, facts: dict[str, Any]) -> Any:
        request = {
            "principal": {"type": "Agent", "id": "agent"},
            "action": action,
            "resource": {"type": "Tool", "id": "tool"},
            "context": facts,
        }
        return self._cedar.is_authorized(request, self._policies, [], schema=self._schema)

    def _first_reason(self, reasons: list[str]) -> str:
        indices = sorted(int(r.removeprefix("policy")) for r in reasons)
        return self._ids[indices[0]]

    def decide(self, facts: dict[str, Any]) -> tuple[DecisionOutcome, str]:
        execute = self._authorize(ACTION_EXECUTE, facts)
        if execute.diagnostics.errors:
            return DecisionOutcome.BLOCK, "cedar-evaluation-error"
        reasons = list(execute.diagnostics.reasons)
        if execute.allowed:
            return DecisionOutcome.ALLOW, self._first_reason(reasons)
        if reasons:
            return DecisionOutcome.BLOCK, self._first_reason(reasons)
        confirm = self._authorize(ACTION_CONFIRM, facts)
        if confirm.diagnostics.errors:
            return DecisionOutcome.BLOCK, "cedar-evaluation-error"
        if confirm.allowed:
            return DecisionOutcome.CONFIRM, self._first_reason(list(confirm.diagnostics.reasons))
        return DecisionOutcome.BLOCK, "cedar-default-deny"

    def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None = None,
        context: PolicyContext | None = None,
    ) -> PolicyResult:
        ctx = context or PolicyContext()
        facts = self.facts(
            tool_name=tool_name,
            arguments=arguments,
            risk_tier=risk_tier,
            agent_id=agent_id,
            ctx=ctx,
        )
        decision, policy_id = self.decide(facts)
        explanation = _EXPLANATIONS.get(policy_id, "Cedar evaluation failed closed.")
        return PolicyResult(
            decision=decision,
            policy_id=policy_id,
            explanation=f"[cedar] {explanation}",
        )
