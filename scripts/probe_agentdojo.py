#!/usr/bin/env python3
"""Probe AgentDojo installability and free/local coverage limits.

This script records what works without paid LLM APIs. It does NOT claim an
AgentDojo score for AgentTaint.
"""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "reports" / "agentdojo_probe.json"


def main() -> int:
    report: dict = {
        "created_at": datetime.now(UTC).isoformat(),
        "goal": "Assess free/local AgentDojo integration feasibility for AgentTaint",
        "steps": [],
        "conclusion": None,
    }

    # Step 1: import
    try:
        import agentdojo  # type: ignore

        report["steps"].append(
            {
                "step": "import_agentdojo",
                "ok": True,
                "version": getattr(agentdojo, "__version__", "unknown"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(
            {
                "step": "import_agentdojo",
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc()[-2000:],
            }
        )
        report["conclusion"] = (
            "AgentDojo package not importable in this environment after install attempt; "
            "no AgentDojo scores produced."
        )
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    # Step 2: list suites if API exists
    suites = None
    try:
        from agentdojo.task_suite.load_suites import get_suites  # type: ignore

        suites = sorted(get_suites("v1.2.2").keys())
        report["steps"].append(
            {
                "step": "list_suites",
                "ok": True,
                "benchmark_version": "v1.2.2",
                "suites": suites,
            }
        )
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(
            {
                "step": "list_suites",
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc()[-2000:],
            }
        )

    # Step 3: document LLM requirement
    report["steps"].append(
        {
            "step": "llm_requirement",
            "ok": True,
            "note": (
                "Stock AgentDojo benchmark scripts require an LLM model "
                "(e.g. gpt-4o). No free local default model is provided by AgentDojo "
                "for full attack/defense evaluation. Running those scripts would "
                "need paid APIs or a separately configured local LLM — out of scope "
                "for this free/local milestone unless a ground-truth/no-model path "
                "is available."
            ),
        }
    )

    # Step 4: check for ground-truth / no-model path
    try:
        import pkgutil

        import agentdojo as ad

        modules = [m.name for m in pkgutil.walk_packages(ad.__path__, ad.__name__ + ".")]
        ground = [m for m in modules if "ground" in m.casefold() or "local" in m.casefold()]
        report["steps"].append(
            {
                "step": "search_ground_truth_modules",
                "ok": True,
                "matches": ground[:50],
                "module_count": len(modules),
            }
        )
    except Exception as exc:  # noqa: BLE001
        report["steps"].append(
            {
                "step": "search_ground_truth_modules",
                "ok": False,
                "error": str(exc),
            }
        )

    report["conclusion"] = (
        "Partial coverage only: AgentDojo can be imported and suites inspected, but a "
        "fair full ASR/utility evaluation was not executed because it requires an LLM "
        "backend beyond the free/local constraint of this milestone. No synthetic "
        "AgentDojo numbers are reported. Custom AgentTaint scenarios remain the "
        "primary measured evidence."
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
