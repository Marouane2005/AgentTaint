"""Load policy configuration from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agenttaint_policy.adapter import ProvenanceAwarePolicy, StubPolicyAdapter


def load_stub_policy(path: str | Path) -> StubPolicyAdapter:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    denylist = {str(x) for x in (raw.get("denylist_tools") or [])}
    blocked = {str(x).strip().lower() for x in (raw.get("blocked_recipients") or [])}
    return StubPolicyAdapter(
        denylist_tools=denylist,
        blocked_recipients=blocked,
        allow_by_default=bool(raw.get("allow_by_default", True)),
        confirm_high_risk=bool(raw.get("confirm_high_risk", False)),
    )


def load_provenance_policy(path: str | Path) -> ProvenanceAwarePolicy:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    denylist = {str(x) for x in (raw.get("denylist_tools") or [])}
    blocked_raw = raw.get("blocked_recipients")
    blocked = (
        {str(x).strip().lower() for x in blocked_raw} if blocked_raw is not None else None
    )
    return ProvenanceAwarePolicy(
        denylist_tools=denylist,
        confirm_untrusted_influence=bool(raw.get("confirm_untrusted_influence", False)),
        fail_closed_unknown_high=bool(raw.get("fail_closed_unknown_high", False)),
        blocked_recipients=blocked,
    )
