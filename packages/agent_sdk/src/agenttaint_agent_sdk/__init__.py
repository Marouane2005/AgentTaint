"""Instrumented AgentTaint SDK for cooperating agents."""

from agenttaint_agent_sdk.confirm_cli import format_confirmation_prompt, interactive_confirm
from agenttaint_agent_sdk.confirmation import (
    ConfirmationError,
    ConfirmationRecord,
    ConfirmationService,
    ConfirmationStatus,
)
from agenttaint_agent_sdk.context import AgentTaintContext
from agenttaint_agent_sdk.envelope import (
    EnvelopeError,
    EnvelopeVerifier,
    NonceStore,
    ProvenanceEnvelope,
)
from agenttaint_agent_sdk.keys import AgentKeyring, KeyringError
from agenttaint_agent_sdk.persistence import (
    DurableConfirmationService,
    DurableNonceStore,
)

__all__ = [
    "AgentKeyring",
    "AgentTaintContext",
    "ConfirmationError",
    "ConfirmationRecord",
    "ConfirmationService",
    "ConfirmationStatus",
    "DurableConfirmationService",
    "DurableNonceStore",
    "EnvelopeError",
    "EnvelopeVerifier",
    "KeyringError",
    "NonceStore",
    "ProvenanceEnvelope",
    "format_confirmation_prompt",
    "interactive_confirm",
]
__version__ = "0.1.0"
