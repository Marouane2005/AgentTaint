"""Policy evaluation context carrying provenance / reconstruction signals."""

from __future__ import annotations

from dataclasses import dataclass, field

from agenttaint_core.schemas import ArgumentEvidence, ProvenanceStatus, RiskTier


@dataclass
class PolicyContext:
    """Inputs for provenance-aware authorization.

    INFERRED evidence may raise scrutiny but must never silently authorize.
    """

    provenance_status: ProvenanceStatus = ProvenanceStatus.UNKNOWN
    has_untrusted_influence: bool = False
    influence_inferred_only: bool = False
    user_authorized_values: set[str] = field(default_factory=set)
    authority_argument_names: set[str] = field(
        default_factory=lambda: {"to", "recipient", "url", "path", "command"}
    )
    argument_evidence: list[ArgumentEvidence] = field(default_factory=list)
    registry_available: bool = True
    confirmation_id: str | None = None
    confirmation_validated: bool = False
    risk_tier: RiskTier | None = None
