"""Defense baselines for the custom benchmark.

These are AgentTaint configurations / reimplementations of coarse ideas—not
faithful replications of CaMeL, FIDES, CapLite, or NeuroTaint.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from agenttaint_core.schemas import DecisionOutcome, Origin, RiskTier
from agenttaint_policy.adapter import PolicyResult, ProvenanceAwarePolicy
from agenttaint_policy.cedar_engine import CedarProvenancePolicy
from agenttaint_policy.context import PolicyContext
from agenttaint_reconstruction.engine import AblationMode

from agenttaint_benchmark.schema import AblationModeName, DefenseMode


@dataclass(frozen=True)
class DefenseConfig:
    mode: DefenseMode
    ablation: AblationModeName = AblationModeName.NONE
    confirm_untrusted_influence: bool = False
    fail_closed_unknown_high: bool = False

    @property
    def use_explicit(self) -> bool:
        return self.mode in {DefenseMode.EXPLICIT_ONLY, DefenseMode.COMBINED}

    @property
    def use_reconstruction(self) -> bool:
        return self.mode in {DefenseMode.RECONSTRUCTION_ONLY, DefenseMode.COMBINED}

    def reconstruction_ablation(self) -> AblationMode | None:
        if not self.use_reconstruction:
            return None
        mapping = {
            AblationModeName.NONE: AblationMode.COMBINED,
            AblationModeName.LEXICAL: AblationMode.LEXICAL,
            AblationModeName.STRUCTURAL: AblationMode.STRUCTURAL,
            AblationModeName.SEMANTIC: AblationMode.SEMANTIC,
            AblationModeName.LEXICAL_STRUCTURAL: AblationMode.LEXICAL_STRUCTURAL,
            AblationModeName.COMBINED: AblationMode.COMBINED,
            AblationModeName.EXPLICIT: AblationMode.EXPLICIT,
        }
        return mapping[self.ablation]


class AllowAllPolicy:
    """Undefended baseline."""

    def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None = None,
        context: PolicyContext | None = None,
    ) -> PolicyResult:
        return PolicyResult(
            decision=DecisionOutcome.ALLOW,
            policy_id="undefended-allow-all",
            explanation="Undefended baseline allows all tool calls.",
        )


class CoarseTaintPolicy:
    """Any UNTRUSTED/UNKNOWN origin observed in session → BLOCK HIGH sinks."""

    def __init__(self) -> None:
        self.seen_untrusted = False

    def mark_origins(self, origins: set[Origin]) -> None:
        if origins & {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN}:
            self.seen_untrusted = True

    def evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        risk_tier: RiskTier,
        agent_id: str | None = None,
        context: PolicyContext | None = None,
    ) -> PolicyResult:
        if risk_tier == RiskTier.HIGH and self.seen_untrusted:
            return PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="coarse-taint-block",
                explanation=(
                    "Coarse taint: untrusted content was observed earlier in the "
                    "session; blocking high-risk sink."
                ),
            )
        return PolicyResult(
            decision=DecisionOutcome.ALLOW,
            policy_id="coarse-taint-allow",
            explanation="Coarse taint: no prior untrusted observation or non-high risk.",
        )


def build_policy(config: DefenseConfig) -> Any:
    if config.mode == DefenseMode.UNDEFENDED:
        return AllowAllPolicy()
    if config.mode == DefenseMode.COARSE_TAINT:
        return CoarseTaintPolicy()
    # Explicit / reconstruction / combined share ProvenanceAwarePolicy;
    # differences are in which evidence the gateway supplies.
    reference = ProvenanceAwarePolicy(
        denylist_tools=set(),
        blocked_recipients=set(),  # measure provenance, not static denylist
        confirm_untrusted_influence=config.confirm_untrusted_influence,
        fail_closed_unknown_high=config.fail_closed_unknown_high,
    )
    if os.environ.get("AGENTTAINT_POLICY_ENGINE", "cedar").strip().lower() == "python":
        return reference
    return CedarProvenancePolicy.from_reference(reference)


def default_defense_matrix() -> list[DefenseConfig]:
    return [
        DefenseConfig(DefenseMode.UNDEFENDED),
        DefenseConfig(DefenseMode.COARSE_TAINT),
        DefenseConfig(DefenseMode.EXPLICIT_ONLY),
        DefenseConfig(DefenseMode.RECONSTRUCTION_ONLY, AblationModeName.COMBINED),
        DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED),
    ]


def ablation_matrix() -> list[DefenseConfig]:
    """Reconstruction-channel ablations under reconstruction_only defense.

    Excludes COMBINED (already covered in the primary defense matrix).
    Includes EXPLICIT so M13 can isolate lineage-only reconstruction evidence.
    """
    modes = [
        AblationModeName.LEXICAL,
        AblationModeName.STRUCTURAL,
        AblationModeName.SEMANTIC,
        AblationModeName.LEXICAL_STRUCTURAL,
        AblationModeName.EXPLICIT,
    ]
    return [DefenseConfig(DefenseMode.RECONSTRUCTION_ONLY, ablation=m) for m in modes]
