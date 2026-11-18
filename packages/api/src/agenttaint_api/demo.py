"""Public demo mode: read-only console, runnable synthetic scenarios.

Enabled with ``AGENTTAINT_DEMO_MODE=1``. Every tool is a mock (no shell, no
network, no Docker); approvals and session resets are disabled; requests are
rate-limited. Scenario runs go through the real gateway and Cedar policy.
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from itertools import count
from typing import Any

from agenttaint_api import state as state_mod

MAX_TRACES = 200
_LOCK = threading.Lock()
_RUN_IDS = count(1)


def demo_mode() -> bool:
    return os.environ.get("AGENTTAINT_DEMO_MODE", "").strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def _scenarios() -> dict[str, Any]:
    """Curated catalogue: one scenario per family plus reconstruction/challenge cases."""
    from agenttaint_benchmark.loader import load_scenarios

    picked: dict[str, Any] = {}
    seen: set[tuple[str, str]] = set()
    _, test = load_scenarios("test")
    for sc in test:
        key = (sc.kind.value, sc.family.value)
        if key not in seen:
            seen.add(key)
            picked[sc.scenario_id] = sc
    _, rec = load_scenarios("reconstruction")
    for kind in ("attack", "benign"):
        sc = next(s for s in rec if s.kind.value == kind)
        picked[sc.scenario_id] = sc
    _, challenge = load_scenarios("challenge")
    for sc in challenge:
        picked[sc.scenario_id] = sc
    return picked


def catalog() -> list[dict[str, Any]]:
    out = []
    for sc in _scenarios().values():
        out.append(
            {
                "scenario_id": sc.scenario_id,
                "kind": sc.kind.value,
                "family": sc.family.value,
                "split": sc.split.value,
                "description": sc.description,
                "difficulty": sc.difficulty,
                "send_to": sc.send_to,
            }
        )
    out.sort(key=lambda d: (d["kind"] != "attack", d["split"], d["family"]))
    return out


def _defenses() -> tuple[Any, Any]:
    from agenttaint_benchmark.defenses import DefenseConfig
    from agenttaint_benchmark.schema import AblationModeName, DefenseMode

    return (
        DefenseConfig(DefenseMode.UNDEFENDED, AblationModeName.NONE),
        DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED),
    )


def run(scenario_id: str) -> dict[str, Any]:
    """Run one scenario undefended (throwaway stores) and with AgentTaint (shared)."""
    from agenttaint_benchmark.runner import run_scenario

    scenario = _scenarios().get(scenario_id)
    if scenario is None:
        raise KeyError(scenario_id)
    undefended_cfg, combined_cfg = _defenses()
    baseline = run_scenario(scenario, undefended_cfg)
    with _LOCK:
        current = state_mod.get_state()
        if len(current.traces) >= MAX_TRACES:
            state_mod.seed_demo_session()
            current = state_mod.get_state()
        trace_id = f"{scenario.scenario_id}#run{next(_RUN_IDS)}"
        result, trace = state_mod.replay_scenario(
            current, scenario, combined_cfg, None, source="visitor_run", trace_id=trace_id
        )
        current.session.notes = [*current.session.notes[-4:], f"Visitor ran {scenario_id}."]
    return {
        "scenario": next(c for c in catalog() if c["scenario_id"] == scenario_id),
        "trace_id": trace["trace_id"],
        "call_ids": trace["call_ids"],
        "without_agenttaint": {
            "decision": baseline.decision,
            "attack_success": baseline.attack_success,
            "benign_completed": baseline.benign_completed,
        },
        "with_agenttaint": {
            "decision": result.decision,
            "policy_id": result.policy_id,
            "attack_success": result.attack_success,
            "benign_completed": result.benign_completed,
            "evidence_statuses": result.evidence_statuses,
            "latency_ms": round(result.latency_ms, 2),
        },
    }


def seed_if_empty() -> None:
    with _LOCK:
        if state_mod.get_state().session.mode == "empty":
            state_mod.seed_demo_session()
