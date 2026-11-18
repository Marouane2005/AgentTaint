"""Honest stubs for AgentDojo / InjecAgent integration.

These adapters intentionally refuse to invent scores. Full evaluation requires
LLM-backed protocols outside the free/local default stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ExternalBenchmarkNotEvaluated(RuntimeError):
    """Raised when an external benchmark cannot be run under free/local constraints."""


@dataclass(frozen=True)
class ExternalFeasibility:
    name: str
    importable: bool
    free_local_asr_possible: bool
    blockers: list[str]
    adapter_status: str


def probe_agentdojo() -> ExternalFeasibility:
    blockers: list[str] = []
    importable = False
    try:
        import agentdojo  # noqa: F401

        importable = True
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"import failed: {exc}")
    if importable:
        blockers.append(
            "Official AgentDojo benchmark runner requires an LLM model integration "
            "(hosted API or self-hosted model wired into AgentDojo's model enum)."
        )
        blockers.append(
            "A fair AgentTaint comparison needs a defense wrapper around AgentDojo "
            "tools that preserves the official task/attack protocol without modification."
        )
    return ExternalFeasibility(
        name="AgentDojo",
        importable=importable,
        free_local_asr_possible=False,
        blockers=blockers
        or ["LLM-backed protocol required; free/local ASR not available in default stack"],
        adapter_status="stub-only (refuses evaluation without LLM harness)",
    )


def probe_injecagent() -> ExternalFeasibility:
    blockers: list[str] = []
    importable = False
    try:
        import injecagent  # noqa: F401

        importable = True
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"import failed: {exc}")
    blockers.append(
        "InjecAgent-style suites require an LLM agent harness and matching attack "
        "definitions; none are bundled in the free/local AgentTaint default install."
    )
    return ExternalFeasibility(
        name="InjecAgent",
        importable=importable,
        free_local_asr_possible=False,
        blockers=blockers,
        adapter_status="stub-only (refuses evaluation without LLM harness)",
    )


def run_agentdojo_adapter(**_kwargs: Any) -> None:
    """Refuse to fabricate AgentDojo scores."""
    feasibility = probe_agentdojo()
    raise ExternalBenchmarkNotEvaluated(
        "AgentDojo: not evaluated. " + "; ".join(feasibility.blockers)
    )


def run_injecagent_adapter(**_kwargs: Any) -> None:
    """Refuse to fabricate InjecAgent scores."""
    feasibility = probe_injecagent()
    raise ExternalBenchmarkNotEvaluated(
        "InjecAgent: not evaluated. " + "; ".join(feasibility.blockers)
    )
