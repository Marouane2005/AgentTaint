"""Risk tiers from trust registry + optional argument features.

Classification is deterministic and auditable. No LLM involvement.
"""

from __future__ import annotations

from typing import Any

from agenttaint_core.schemas import RiskTier
from agenttaint_provenance.trust import TrustRegistry

# Paths that are sensitive even when the tool's base risk is MEDIUM.
_SENSITIVE_PATH_TOKENS = (
    "../",
    "/etc/",
    ".ssh",
    ".bashrc",
    ".profile",
    ".zshrc",
    "authorized_keys",
    "/root/",
    "id_rsa",
    "id_ed25519",
    ".gnupg",
    ".aws/",
    ".kube/",
)


class RiskClassifier:
    def __init__(self, trust: TrustRegistry) -> None:
        self.trust = trust

    def classify(self, tool_name: str, arguments: dict[str, Any] | None = None) -> RiskTier:
        base = self.trust.risk_for(tool_name)
        args = arguments or {}

        # Escalate http.get when destination looks non-local (authority-like).
        if tool_name == "http.get":
            url = str(args.get("url", ""))
            if url.startswith("http://") or url.startswith("https://"):
                if not any(host in url for host in ("127.0.0.1", "localhost", "[::1]")):
                    return RiskTier.MEDIUM

        if tool_name == "filesystem.write":
            path = str(args.get("path", "")).casefold()
            if any(tok in path for tok in _SENSITIVE_PATH_TOKENS):
                return RiskTier.HIGH

        return base
