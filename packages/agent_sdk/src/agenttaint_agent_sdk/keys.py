"""Per-agent HMAC secrets for provenance envelopes.

A single shared secret lets any holder forge `sender_agent`. The keyring binds
each cooperating agent to its own secret so signatures are agent-scoped.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class KeyringError(PermissionError):
    pass


@dataclass
class AgentKeyring:
    """Map agent_id → HMAC secret. Unknown agents fail closed."""

    secrets: dict[str, str] = field(default_factory=dict)
    # Optional fallback for migration / single-agent demos. Prefer empty.
    default_secret: str | None = None

    def add(self, agent_id: str, secret: str) -> None:
        if not agent_id or not secret:
            raise KeyringError("agent_id and secret are required")
        self.secrets[agent_id] = secret

    def secret_for(self, agent_id: str) -> str:
        if agent_id in self.secrets:
            return self.secrets[agent_id]
        if self.default_secret is not None:
            return self.default_secret
        raise KeyringError(f"no envelope secret for agent: {agent_id}")

    def has(self, agent_id: str) -> bool:
        return agent_id in self.secrets or self.default_secret is not None
