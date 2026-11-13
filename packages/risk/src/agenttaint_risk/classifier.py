"""Risk tiers from trust registry + optional argument features.

Classification is deterministic and auditable. No LLM involvement.
"""

from __future__ import annotations

from agenttaint_core.schemas import RiskTier
from agenttaint_provenance.trust import TrustRegistry


class RiskClassifier:
    def __init__(self, trust: TrustRegistry) -> None:
        self.trust = trust

    def classify(self, tool_name: str, arguments: dict | None = None) -> RiskTier:
        base = self.trust.risk_for(tool_name)
        args = arguments or {}

        # Escalate http.get when destination looks non-local (authority-like).
        if tool_name == "http.get":
            url = str(args.get("url", ""))
            if url.startswith("http://") or url.startswith("https://"):
                if not any(
                    host in url
                    for host in ("127.0.0.1", "localhost", "[::1]")
                ):
                    return RiskTier.MEDIUM

        if tool_name == "filesystem.write":
            path = str(args.get("path", ""))
            if any(tok in path for tok in ("../", "/etc/", ".ssh")):
                return RiskTier.HIGH

        return base
