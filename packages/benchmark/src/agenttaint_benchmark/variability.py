"""Multi-seed bootstrap variability for fixed held-out corpora."""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable

from agenttaint_benchmark.metrics import aggregate
from agenttaint_benchmark.schema import (
    AggregateMetrics,
    Scenario,
    ScenarioRunResult,
    SeedAggregate,
    VariabilitySummary,
)


def bootstrap_sample(
    scenarios: list[Scenario],
    *,
    seed: int,
) -> list[Scenario]:
    """Resample scenarios with replacement (same length as corpus)."""
    rng = random.Random(seed)
    return [scenarios[rng.randrange(len(scenarios))] for _ in scenarios]


def summarize_variability(
    seed_runs: Iterable[SeedAggregate],
    *,
    defenses: list[str],
    metrics: list[str] | None = None,
) -> list[VariabilitySummary]:
    metric_names = metrics or [
        "asr",
        "utility",
        "fpr_block",
        "fpr_confirm",
        "provenance_f1",
        "latency_ms_median",
    ]
    runs = list(seed_runs)
    out: list[VariabilitySummary] = []
    for defense in defenses:
        for metric in metric_names:
            values: list[float] = []
            for run in runs:
                agg = run.per_defense.get(defense)
                if agg is None:
                    continue
                raw = getattr(agg, metric, None)
                if raw is None:
                    continue
                values.append(float(raw))
            if not values:
                out.append(
                    VariabilitySummary(
                        metric=metric,
                        defense=defense,
                        n_seeds=len(runs),
                    )
                )
                continue
            out.append(
                VariabilitySummary(
                    metric=metric,
                    defense=defense,
                    mean=statistics.fmean(values),
                    std=statistics.pstdev(values) if len(values) > 1 else 0.0,
                    min=min(values),
                    max=max(values),
                    n_seeds=len(values),
                )
            )
    return out


def aggregate_from_ids(
    full_results: list[ScenarioRunResult],
    sampled_ids: list[str],
    *,
    defense_key: str,
) -> AggregateMetrics:
    """Map bootstrap scenario ids back to already-computed per-scenario results.

    Uses the first matching result for each id under the defense key
    (`defense` or `defense:ablation`).
    """
    by_id: dict[str, ScenarioRunResult] = {}
    for row in full_results:
        key = row.defense
        if row.ablation not in {"none", ""}:
            key = f"{row.defense}:{row.ablation}"
        if key != defense_key:
            # Also allow exact defense-only keys for undefended/coarse/explicit
            if not (row.ablation in {"none", ""} and row.defense == defense_key):
                continue
        if row.scenario_id not in by_id:
            by_id[row.scenario_id] = row
    sampled_rows = []
    for sid in sampled_ids:
        if sid in by_id:
            sampled_rows.append(by_id[sid])
    return aggregate(sampled_rows)
