"""Enforcement boundary errors."""

from __future__ import annotations

from agenttaint_core.schemas import ToolCallDecision


class EnforcementError(PermissionError):
    """Raised when the proxy blocks or requires confirmation for a tool call."""

    def __init__(self, message: str, decision: ToolCallDecision) -> None:
        super().__init__(message)
        self.decision = decision
