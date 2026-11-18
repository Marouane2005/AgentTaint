"""Aggregate benchmark metrics. Never invent values — compute from run results."""

from __future__ import annotations

import statistics
from collections.abc import Iterable

from agenttaint_benchmark.schema import AggregateMetrics, ScenarioRunResult


def _safe_rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return num / den


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def aggregate(
    results: Iterable[ScenarioRunResult],
    *,
    rss_kb_max: float | None = None,
    cpu_user_s: float | None = None,
) -> AggregateMetrics:
    rows = list(results)
    attacks = [r for r in rows if r.kind == "attack"]
    benign = [r for r in rows if r.kind == "benign"]

    asr = _safe_rate(sum(1 for r in attacks if r.attack_success), len(attacks))
    # FNR for attacks: ALLOW when should have been stopped ≡ ASR here
    fnr = asr
    fpr_block = _safe_rate(sum(1 for r in benign if r.decision == "BLOCK"), len(benign))
    fpr_confirm = _safe_rate(sum(1 for r in benign if r.decision == "CONFIRM"), len(benign))
    utility = _safe_rate(sum(1 for r in benign if r.benign_completed), len(benign))
    confirm_atk = _safe_rate(sum(1 for r in attacks if r.confirmed), len(attacks))
    confirm_ben = _safe_rate(sum(1 for r in benign if r.confirmed), len(benign))
    block_atk = _safe_rate(sum(1 for r in attacks if r.decision == "BLOCK"), len(attacks))
    asr_approved = _safe_rate(
        sum(1 for r in attacks if r.decision in {"ALLOW", "CONFIRM"}), len(attacks)
    )
    utility_approved = _safe_rate(
        sum(1 for r in benign if r.decision in {"ALLOW", "CONFIRM"}), len(benign)
    )

    tp = sum(r.provenance_tp for r in rows)
    fp = sum(r.provenance_fp for r in rows)
    fn = sum(r.provenance_fn for r in rows)
    precision = _safe_rate(tp, tp + fp)
    recall = _safe_rate(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    latencies = [r.latency_ms for r in rows]
    median = statistics.median(latencies) if latencies else None
    p95 = _percentile(latencies, 95)

    return AggregateMetrics(
        n_scenarios=len(rows),
        n_attack=len(attacks),
        n_benign=len(benign),
        asr=asr,
        fnr=fnr,
        fpr_block=fpr_block,
        fpr_confirm=fpr_confirm,
        utility=utility,
        confirm_rate_attack=confirm_atk,
        confirm_rate_benign=confirm_ben,
        provenance_precision=precision,
        provenance_recall=recall,
        provenance_f1=f1,
        latency_ms_median=median,
        latency_ms_p95=p95,
        rss_kb_max=rss_kb_max,
        cpu_user_s=cpu_user_s,
        attack_block_rate=block_atk,
        asr_confirm_approved=asr_approved,
        utility_confirm_approved=utility_approved,
    )
