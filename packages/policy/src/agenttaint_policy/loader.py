"""Load policy configuration from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agenttaint_policy.adapter import PolicyAdapter, ProvenanceAwarePolicy, StubPolicyAdapter
from agenttaint_policy.cedar_engine import CedarProvenancePolicy


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
    blocked = {str(x).strip().lower() for x in blocked_raw} if blocked_raw is not None else None
    return ProvenanceAwarePolicy(
        denylist_tools=denylist,
        confirm_untrusted_influence=bool(raw.get("confirm_untrusted_influence", False)),
        fail_closed_unknown_high=bool(raw.get("fail_closed_unknown_high", False)),
        blocked_recipients=blocked,
        confirm_medium_untrusted=bool(raw.get("confirm_medium_untrusted", True)),
        scrutinize_medium_undeclared=bool(raw.get("scrutinize_medium_undeclared", True)),
        fail_closed_unknown_medium=bool(raw.get("fail_closed_unknown_medium", False)),
    )


POLICY_ENGINES = ("cedar", "python")


def load_policy(path: str | Path) -> PolicyAdapter:
    """Load the configured provenance policy engine (default: Cedar).

    ``engine: python`` selects the reference implementation. Unknown engines are
    rejected rather than silently falling back.
    """
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    engine = str(raw.get("engine", "cedar")).strip().lower()
    if engine not in POLICY_ENGINES:
        raise ValueError(f"unknown policy engine {engine!r}; expected one of {POLICY_ENGINES}")
    reference = load_provenance_policy(path)
    if engine == "python":
        return reference
    return CedarProvenancePolicy.from_reference(reference)
