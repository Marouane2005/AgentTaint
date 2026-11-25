"""Deterministic policy adapters.

ProvenanceAwarePolicy is the executable reference for the Cedar engine
(``cedar_engine.CedarProvenancePolicy``); both must stay in exact parity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agenttaint_core.schemas import DecisionOutcome, ProvenanceStatus, RiskTier

from agenttaint_policy.context import PolicyContext
from agenttaint_policy.grants import grants_cover_authority_arguments


@dataclass(frozen=True)
class PolicyResult:
    decision: DecisionOutcome
    policy_id: str
    explanation: str


class PolicyAdapter(Protocol):
    def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None = None,
        context: PolicyContext | None = None,
    ) -> PolicyResult: ...


@dataclass
class StubPolicyAdapter:
    """Legacy Milestone-2 stub (kept for compatibility)."""

    denylist_tools: set[str]
    blocked_recipients: set[str]
    allow_by_default: bool = True
    confirm_high_risk: bool = False

    def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None = None,
        context: PolicyContext | None = None,
    ) -> PolicyResult:
        if tool_name in self.denylist_tools:
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="denylist-tool",
                explanation=f"Tool '{tool_name}' is on the enforcement denylist.",
            )

        if tool_name == "email.send":
            recipient = str(arguments.get("to", "")).strip().lower()
            if recipient and recipient in self.blocked_recipients:
                return PolicyResult(
                    decision=DecisionOutcome.BLOCK,
                    policy_id="blocked-recipient",
                    explanation=(
                        f"Recipient '{recipient}' is blocked by stub policy "
                        "(untrusted/external destination deny)."
                    ),
                )

        if self.confirm_high_risk and risk_tier == RiskTier.HIGH:
            return PolicyResult(
                decision=DecisionOutcome.CONFIRM,
                policy_id="confirm-high-risk",
                explanation="High-risk operation requires explicit confirmation.",
            )

        if self.allow_by_default:
            return PolicyResult(
                decision=DecisionOutcome.ALLOW,
                policy_id="allow-default",
                explanation="Stub policy allowed the operation.",
            )

        return PolicyResult(
            decision=DecisionOutcome.BLOCK,
            policy_id="deny-default",
            explanation="Stub policy deny-by-default matched.",
        )


@dataclass
class ProvenanceAwarePolicy:
    """Provenance-aware enforcement with structured authorization grants.

    Rules (ordered):
    1. Fail closed if HIGH risk and provenance registry unavailable.
    2. Denylist tools → BLOCK.
    3. Valid bound confirmation → ALLOW.
    4. Blocked recipients (email.send) unless covered by structured grants.
    5. HIGH + structured grants covering every authority argument → ALLOW.
    6. HIGH/MEDIUM + untrusted influence → BLOCK (or CONFIRM if configured).
    7. HIGH + UNKNOWN/PARTIAL without confirmation → CONFIRM (or BLOCK).
    8. HIGH otherwise → CONFIRM.
    9. MEDIUM with undeclared lineage after the session ingested untrusted content
       → CONFIRM (or BLOCK when fail_closed_unknown_medium). Missing lineage is
       treated as UNKNOWN, never as clean.
    10. LOW defaults to ALLOW unless denylist matched.
    """

    denylist_tools: set[str]
    confirm_untrusted_influence: bool = False
    fail_closed_unknown_high: bool = False
    blocked_recipients: set[str] | None = None
    # MEDIUM sinks with untrusted influence default to CONFIRM (safer than ALLOW).
    confirm_medium_untrusted: bool = True
    # MEDIUM sinks whose caller declared no lineage, in a session that has seen
    # untrusted content: CONFIRM by default, BLOCK when fail_closed_unknown_medium.
    scrutinize_medium_undeclared: bool = True
    fail_closed_unknown_medium: bool = False

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
        effective_agent = agent_id or ctx.agent_id

        if risk_tier == RiskTier.HIGH and not ctx.registry_available:
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="fail-closed-registry-unavailable",
                explanation=(
                    "High-risk operation blocked: provenance registry unavailable (fail closed)."
                ),
            )

        if tool_name in self.denylist_tools:
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="denylist-tool",
                explanation=f"Tool '{tool_name}' is on the enforcement denylist.",
            )

        if ctx.confirmation_validated:
            return PolicyResult(
                decision=DecisionOutcome.ALLOW,
                policy_id="confirmation-bound-allow",
                explanation="Bound user confirmation validated for this exact action.",
            )

        granted = self._authority_fully_granted(tool_name, arguments, ctx, agent_id=effective_agent)

        if self.blocked_recipients and tool_name == "email.send":
            recipient = str(arguments.get("to", "")).strip().lower()
            if recipient in self.blocked_recipients and not granted:
                return PolicyResult(
                    decision=DecisionOutcome.BLOCK,
                    policy_id="blocked-recipient",
                    explanation=f"Recipient '{recipient}' is blocked by policy.",
                )

        if risk_tier == RiskTier.HIGH:
            # Structured grants may allow only when every authority argument is covered.
            if granted:
                return PolicyResult(
                    decision=DecisionOutcome.ALLOW,
                    policy_id="allow-high-user-authorized-authority",
                    explanation=(
                        "High-risk authority arguments are covered by structured "
                        "session/agent authorization grants."
                    ),
                )

            untrusted = self._untrusted_decision(ctx, tier_label="high-risk")
            if untrusted is not None:
                return untrusted

            if ctx.provenance_status in {
                ProvenanceStatus.UNKNOWN,
                ProvenanceStatus.PARTIAL,
            }:
                if self.fail_closed_unknown_high:
                    return PolicyResult(
                        decision=DecisionOutcome.BLOCK,
                        policy_id="block-unknown-high-risk",
                        explanation=(
                            "High-risk operation blocked: provenance is "
                            f"{ctx.provenance_status.value} (fail closed)."
                        ),
                    )
                return PolicyResult(
                    decision=DecisionOutcome.CONFIRM,
                    policy_id="confirm-unknown-high-risk",
                    explanation=(
                        "High-risk operation with "
                        f"{ctx.provenance_status.value} provenance requires confirmation."
                    ),
                )

            return PolicyResult(
                decision=DecisionOutcome.CONFIRM,
                policy_id="confirm-high-risk",
                explanation="High-risk operation requires explicit bound confirmation.",
            )

        if risk_tier == RiskTier.MEDIUM:
            # Untrusted influence on destinations, paths, or content must not silently ALLOW.
            if ctx.has_untrusted_influence:
                if granted and not ctx.influence_inferred_only:
                    # Explicit grants can still authorize MEDIUM destinations.
                    return PolicyResult(
                        decision=DecisionOutcome.ALLOW,
                        policy_id="allow-medium-user-authorized-authority",
                        explanation=(
                            "Medium-risk authority arguments covered by structured grants."
                        ),
                    )
                if self.confirm_medium_untrusted or self.confirm_untrusted_influence:
                    if ctx.influence_inferred_only:
                        return PolicyResult(
                            decision=DecisionOutcome.CONFIRM,
                            policy_id="confirm-medium-inferred-untrusted",
                            explanation=(
                                "MEDIUM sink with INFERRED untrusted influence on "
                                "destination/path/content; confirmation required."
                            ),
                        )
                    return PolicyResult(
                        decision=DecisionOutcome.CONFIRM,
                        policy_id="confirm-medium-untrusted-influence",
                        explanation=(
                            "MEDIUM sink with untrusted influence on destination, "
                            "path, or content; confirmation required."
                        ),
                    )
                return PolicyResult(
                    decision=DecisionOutcome.BLOCK,
                    policy_id="block-medium-untrusted-influence",
                    explanation=(
                        "Blocked: untrusted information influenced a MEDIUM sink "
                        "without structured authorization."
                    ),
                )

            if (
                self.scrutinize_medium_undeclared
                and not ctx.lineage_declared
                and ctx.session_untrusted_seen
                and not granted
            ):
                if self.fail_closed_unknown_medium:
                    return PolicyResult(
                        decision=DecisionOutcome.BLOCK,
                        policy_id="block-medium-undeclared-lineage",
                        explanation=(
                            "Blocked: MEDIUM sink with undeclared (UNKNOWN) lineage after "
                            "the session ingested untrusted content (fail closed)."
                        ),
                    )
                return PolicyResult(
                    decision=DecisionOutcome.CONFIRM,
                    policy_id="confirm-medium-undeclared-lineage",
                    explanation=(
                        "MEDIUM sink with undeclared (UNKNOWN) lineage after the session "
                        "ingested untrusted content; confirmation required."
                    ),
                )

        return PolicyResult(
            decision=DecisionOutcome.ALLOW,
            policy_id="allow-low" if risk_tier == RiskTier.LOW else "allow-medium",
            explanation="Non-high-risk operation allowed under provenance-aware policy.",
        )

    def _authority_fully_granted(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: PolicyContext,
        *,
        agent_id: str | None,
    ) -> bool:
        if not ctx.authorization_grants:
            return False
        return grants_cover_authority_arguments(
            grants=ctx.authorization_grants,
            tool_name=tool_name,
            arguments=arguments,
            authority_argument_names=ctx.authority_argument_names,
            agent_id=agent_id,
            session_id=ctx.session_id,
        )

    def _untrusted_decision(self, ctx: PolicyContext, *, tier_label: str) -> PolicyResult | None:
        if not ctx.has_untrusted_influence:
            return None
        if ctx.influence_inferred_only:
            if self.confirm_untrusted_influence:
                return PolicyResult(
                    decision=DecisionOutcome.CONFIRM,
                    policy_id="confirm-inferred-untrusted-influence",
                    explanation=(
                        f"INFERRED untrusted influence on a {tier_label} action; "
                        "requires bound confirmation (inference ≠ authorization)."
                    ),
                )
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="block-inferred-untrusted-influence",
                explanation=(
                    f"Blocked: INFERRED untrusted influence cannot authorize {tier_label} actions."
                ),
            )
        if self.confirm_untrusted_influence:
            return PolicyResult(
                decision=DecisionOutcome.CONFIRM,
                policy_id="confirm-untrusted-influence",
                explanation=(
                    f"Untrusted provenance influenced a {tier_label} authority "
                    "or content argument; confirmation required."
                ),
            )
        return PolicyResult(
            decision=DecisionOutcome.BLOCK,
            policy_id="block-untrusted-influence",
            explanation=(
                f"Blocked: untrusted information influenced a {tier_label} action "
                "without explicit structured USER authorization."
            ),
        )
