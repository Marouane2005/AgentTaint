"""Policy evaluation context carrying provenance / reconstruction signals."""

from __future__ import annotations

from dataclasses import dataclass, field

from agenttaint_core.schemas import ArgumentEvidence, ProvenanceStatus, RiskTier

from agenttaint_policy.grants import AuthorizationGrant

# Arguments that decide *where* data goes or *what* gets executed. A grant must cover
# every one that is present, so a grant on ``to`` never silently covers ``bcc``.
DEFAULT_AUTHORITY_ARGUMENTS = frozenset(
    {
        "to",
        "cc",
        "bcc",
        "recipient",
        "recipients",
        "url",
        "uri",
        "endpoint",
        "path",
        "cwd",
        "target",
        "command",
        "args",
        "host",
        "destination",
    }
)
DEFAULT_CONTENT_ARGUMENTS = frozenset({"body", "content", "attachment", "data", "payload"})


@dataclass
class PolicyContext:
    """Inputs for provenance-aware authorization.

    INFERRED evidence may raise scrutiny but must never silently authorize.
    USER authorization is structured grants only — never scraped free-text tokens.
    """

    provenance_status: ProvenanceStatus = ProvenanceStatus.UNKNOWN
    has_untrusted_influence: bool = False
    influence_inferred_only: bool = False
    authorization_grants: list[AuthorizationGrant] = field(default_factory=list)
    # Deprecated compatibility mirror of grant values (tests/docs only).
    user_authorized_values: set[str] = field(default_factory=set)
    authority_argument_names: set[str] = field(
        default_factory=lambda: set(DEFAULT_AUTHORITY_ARGUMENTS)
    )
    content_argument_names: set[str] = field(default_factory=lambda: set(DEFAULT_CONTENT_ARGUMENTS))
    argument_evidence: list[ArgumentEvidence] = field(default_factory=list)
    registry_available: bool = True
    confirmation_id: str | None = None
    confirmation_validated: bool = False
    risk_tier: RiskTier | None = None
    agent_id: str | None = None
    session_id: str | None = None
    tool_name: str | None = None
    # False when the caller declared no argument parent spans for this call.
    lineage_declared: bool = True
    # True when the enforcing session has already ingested untrusted content.
    session_untrusted_seen: bool = False
