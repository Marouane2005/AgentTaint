"""Policy evaluation adapters for AgentTaint."""

from agenttaint_policy.adapter import (
    PolicyAdapter,
    PolicyResult,
    ProvenanceAwarePolicy,
    StubPolicyAdapter,
)
from agenttaint_policy.context import PolicyContext
from agenttaint_policy.evidence import build_policy_context
from agenttaint_policy.grants import AuthorizationGrant, grants_cover_authority_arguments
from agenttaint_policy.loader import load_provenance_policy, load_stub_policy

__all__ = [
    "AuthorizationGrant",
    "PolicyAdapter",
    "PolicyContext",
    "PolicyResult",
    "ProvenanceAwarePolicy",
    "StubPolicyAdapter",
    "build_policy_context",
    "grants_cover_authority_arguments",
    "load_provenance_policy",
    "load_stub_policy",
]
__version__ = "0.1.0"
