"""Load committed scenario JSON (evaluation must not regenerate datasets)."""

from __future__ import annotations

import json
from pathlib import Path

from agenttaint_benchmark.schema import Scenario, Split

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA = ROOT / "benchmarks" / "data"


def dataset_version(data_dir: Path | None = None) -> str:
    path = (data_dir or DEFAULT_DATA) / "VERSION"
    return path.read_text(encoding="utf-8").strip()


def load_scenarios(
    split: Split | str,
    *,
    data_dir: Path | None = None,
) -> tuple[str, list[Scenario]]:
    split_name = split.value if isinstance(split, Split) else split
    base = data_dir or DEFAULT_DATA
    path = base / f"scenarios_{split_name}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    version = str(raw.get("dataset_version") or dataset_version(base))
    scenarios = [Scenario.model_validate(item) for item in raw["scenarios"]]
    for sc in scenarios:
        if sc.split.value != split_name:
            raise ValueError(
                f"scenario {sc.scenario_id} has split={sc.split} expected {split_name}"
            )
    return version, scenarios
