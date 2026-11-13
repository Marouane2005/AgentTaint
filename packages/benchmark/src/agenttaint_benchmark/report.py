"""Write reproducible benchmark reports (JSON + markdown tables)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agenttaint_benchmark.schema import AggregateMetrics, BenchmarkReport


def _fmt_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def metrics_table(per: dict[str, AggregateMetrics]) -> str:
    headers = [
        "config",
        "n",
        "ASR",
        "FNR",
        "FPR_block",
        "FPR_confirm",
        "utility",
        "P",
        "R",
        "F1",
        "lat_med_ms",
        "lat_p95_ms",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for name, m in sorted(per.items()):
        row = [
            name,
            str(m.n_scenarios),
            _fmt_rate(m.asr),
            _fmt_rate(m.fnr),
            _fmt_rate(m.fpr_block),
            _fmt_rate(m.fpr_confirm),
            _fmt_rate(m.utility),
            _fmt_rate(m.provenance_precision),
            _fmt_rate(m.provenance_recall),
            _fmt_rate(m.provenance_f1),
            _fmt_ms(m.latency_ms_median),
            _fmt_ms(m.latency_ms_p95),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_report(report: BenchmarkReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"report_{report.split}_{report.report_id[:8]}.json"
    md_path = out_dir / f"report_{report.split}_{report.report_id[:8]}.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )

    md: list[str] = [
        f"# AgentTaint Benchmark Report (`{report.split}`)",
        "",
        f"- **report_id:** `{report.report_id}`",
        f"- **created_at:** `{report.created_at.isoformat()}`",
        f"- **dataset_version:** `{report.dataset_version}`",
        f"- **seed:** `{report.seed}`",
        f"- **command:** `{report.command}`",
        "",
        "## Per-defense metrics",
        "",
        metrics_table(report.per_defense),
        "",
    ]
    if report.per_ablation:
        md.extend(
            [
                "## Reconstruction ablations (`reconstruction_only`)",
                "",
                metrics_table(report.per_ablation),
                "",
            ]
        )
    if report.per_family_combined:
        md.extend(
            [
                "## Per-family metrics (`combined`)",
                "",
                metrics_table(report.per_family_combined),
                "",
            ]
        )
    if report.challenge_results:
        md.extend(
            [
                "## Challenge probes (not held-out scoring)",
                "",
                "| scenario | defense | decision | attack_success | notes |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for r in report.challenge_results:
            if r.defense in {
                "undefended",
                "coarse_taint",
                "explicit_only",
                "reconstruction_only",
                "combined",
            } and r.ablation in {"none", "combined"}:
                md.append(
                    f"| {r.scenario_id} | {r.defense}:{r.ablation} | {r.decision} | "
                    f"{r.attack_success} | {r.policy_id or ''} |"
                )
        md.append("")
    md.extend(["## Limitations (recorded with run)", ""])
    for item in report.limitations:
        md.append(f"- {item}")
    md.append("")
    if report.notes:
        md.extend(["## Notes", ""])
        for item in report.notes:
            md.append(f"- {item}")
        md.append("")
    md_path.write_text("\n".join(md), encoding="utf-8")
    return json_path, md_path


def latest_symlink(path: Path, link_name: str) -> None:
    link = path.parent / link_name
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(path.name)


def dump_config(config: dict[str, Any]) -> dict[str, Any]:
    return dict(config)
