"""Deterministic policy adapter interface.

Cedar will implement the same interface in a later milestone.
Do not claim Cedar enforcement until that backend exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agenttaint_core.schemas import DecisionOutcome, RiskTier


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
    ) -> PolicyResult: ...


@dataclass
class StubPolicyAdapter:
    """Milestone-2 stub: allow by default, honor denylist and blocked recipients."""

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
