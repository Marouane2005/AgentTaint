"""Policy evaluation adapters for AgentTaint."""

from agenttaint_policy.adapter import PolicyAdapter, PolicyResult, StubPolicyAdapter
from agenttaint_policy.loader import load_stub_policy

__all__ = [
    "PolicyAdapter",
    "PolicyResult",
    "StubPolicyAdapter",
    "load_stub_policy",
]
__version__ = "0.1.0"
