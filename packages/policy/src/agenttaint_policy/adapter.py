"""Deterministic policy adapters.

Cedar is deferred — do not claim Cedar enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agenttaint_core.schemas import DecisionOutcome, ProvenanceStatus, RiskTier

from agenttaint_policy.context import PolicyContext


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
    """Milestone-5 policy: reconstruction evidence informs scrutiny, never silent trust.

    Rules (ordered):
    1. Fail closed if HIGH risk and provenance registry unavailable.
    2. Denylist tools → BLOCK.
    3. Valid bound confirmation → ALLOW.
    4. HIGH + authority arg matching USER-authorized value → ALLOW.
    5. HIGH + untrusted influence (KNOWN or INFERRED) without USER auth → BLOCK
       (or CONFIRM if confirm_untrusted_influence=True).
    6. HIGH + UNKNOWN/PARTIAL without confirmation → CONFIRM (or BLOCK if fail_closed_unknown).
    7. INFERRED-only influence never alone ALLOWs HIGH risk.
    8. LOW/MEDIUM defaults to ALLOW unless denylist matched.
    """

    denylist_tools: set[str]
    confirm_untrusted_influence: bool = False
    fail_closed_unknown_high: bool = False
    blocked_recipients: set[str] | None = None

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

        if risk_tier == RiskTier.HIGH and not ctx.registry_available:
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="fail-closed-registry-unavailable",
                explanation=(
                    "High-risk operation blocked: provenance registry unavailable "
                    "(fail closed)."
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

        if self.blocked_recipients and tool_name == "email.send":
            recipient = str(arguments.get("to", "")).strip().lower()
            if recipient in self.blocked_recipients:
                # Still allow if explicitly user-authorized below.
                if recipient not in {v.lower() for v in ctx.user_authorized_values}:
                    return PolicyResult(
                        decision=DecisionOutcome.BLOCK,
                        policy_id="blocked-recipient",
                        explanation=f"Recipient '{recipient}' is blocked by policy.",
                    )

        if risk_tier == RiskTier.HIGH:
            # USER grounding for authority arguments.
            if self._authority_user_authorized(arguments, ctx):
                return PolicyResult(
                    decision=DecisionOutcome.ALLOW,
                    policy_id="allow-user-authorized-authority",
                    explanation=(
                        "High-risk authority argument matches an explicit USER span value."
                    ),
                )

            if ctx.has_untrusted_influence:
                # INFERRED or KNOWN untrusted influence without USER auth.
                if ctx.influence_inferred_only:
                    # Never silently promote / authorize on inference alone.
                    if self.confirm_untrusted_influence:
                        return PolicyResult(
                            decision=DecisionOutcome.CONFIRM,
                            policy_id="confirm-inferred-untrusted-influence",
                            explanation=(
                                "INFERRED untrusted influence on a high-risk action; "
                                "requires bound confirmation (inference ≠ authorization)."
                            ),
                        )
                    return PolicyResult(
                        decision=DecisionOutcome.BLOCK,
                        policy_id="block-inferred-untrusted-influence",
                        explanation=(
                            "Blocked: INFERRED untrusted influence cannot authorize "
                            "high-risk actions."
                        ),
                    )
                if self.confirm_untrusted_influence:
                    return PolicyResult(
                        decision=DecisionOutcome.CONFIRM,
                        policy_id="confirm-untrusted-influence",
                        explanation=(
                            "Untrusted provenance influenced a high-risk authority "
                            "argument; confirmation required."
                        ),
                    )
                return PolicyResult(
                    decision=DecisionOutcome.BLOCK,
                    policy_id="block-untrusted-influence",
                    explanation=(
                        "Blocked: untrusted information influenced a high-risk action "
                        "without explicit USER authorization."
                    ),
                )

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

            # HIGH with no untrusted influence and KNOWN/clean → still confirm by default
            # for irreversible sinks unless authority was user-authorized (handled above).
            return PolicyResult(
                decision=DecisionOutcome.CONFIRM,
                policy_id="confirm-high-risk",
                explanation="High-risk operation requires explicit bound confirmation.",
            )

        return PolicyResult(
            decision=DecisionOutcome.ALLOW,
            policy_id="allow-low-medium",
            explanation="Non-high-risk operation allowed under provenance-aware policy.",
        )

    def _authority_user_authorized(
        self, arguments: dict[str, Any], ctx: PolicyContext
    ) -> bool:
        if not ctx.user_authorized_values:
            return False
        authorized = {v.strip().casefold() for v in ctx.user_authorized_values}
        for name in ctx.authority_argument_names:
            if name not in arguments:
                continue
            value = str(arguments.get(name, "")).strip().casefold()
            if value and value in authorized:
                return True
        return False
