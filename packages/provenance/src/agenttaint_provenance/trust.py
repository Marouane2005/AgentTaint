"""Trust registry: integration trust ≠ content origin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from agenttaint_core.schemas import Origin, RiskTier


@dataclass(frozen=True)
class ToolTrustEntry:
    tool_name: str
    result_origin: Origin
    default_risk: RiskTier
    integration_trust: str = "UNKNOWN"
    notes: str = ""


@dataclass
class TrustRegistry:
    version: int
    defaults_result_origin: Origin = Origin.UNTRUSTED_TOOL
    defaults_risk: RiskTier = RiskTier.MEDIUM
    tools: dict[str, ToolTrustEntry] = field(default_factory=dict)
    internal_path_prefixes: list[str] = field(default_factory=list)

    def get(self, tool_name: str) -> ToolTrustEntry:
        if tool_name in self.tools:
            return self.tools[tool_name]
        return ToolTrustEntry(
            tool_name=tool_name,
            result_origin=self.defaults_result_origin,
            default_risk=self.defaults_risk,
        )

    def result_origin_for(self, tool_name: str) -> Origin:
        return self.get(tool_name).result_origin

    def risk_for(self, tool_name: str) -> RiskTier:
        return self.get(tool_name).default_risk

    def is_internal_path(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.internal_path_prefixes)


def load_trust_registry(path: str | Path) -> TrustRegistry:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults", {})
    tools: dict[str, ToolTrustEntry] = {}
    for name, cfg in (raw.get("tools") or {}).items():
        default_origin = defaults.get("result_origin", "UNTRUSTED_TOOL")
        default_risk = defaults.get("default_risk", "MEDIUM")
        tools[name] = ToolTrustEntry(
            tool_name=name,
            result_origin=Origin(cfg.get("result_origin", default_origin)),
            default_risk=RiskTier(cfg.get("default_risk", default_risk)),
            integration_trust=str(cfg.get("integration_trust", "UNKNOWN")),
            notes=str(cfg.get("notes", "")),
        )
    return TrustRegistry(
        version=int(raw.get("version", 1)),
        defaults_result_origin=Origin(defaults.get("result_origin", "UNTRUSTED_TOOL")),
        defaults_risk=RiskTier(defaults.get("default_risk", "MEDIUM")),
        tools=tools,
        internal_path_prefixes=list(raw.get("internal_path_prefixes") or []),
    )
