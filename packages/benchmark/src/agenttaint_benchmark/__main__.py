"""CLI: python -m agenttaint_benchmark run --split test --seed 2120"""

from __future__ import annotations

import argparse
import resource
import sys
from pathlib import Path

from agenttaint_benchmark.defenses import (
    ablation_matrix,
    default_defense_matrix,
)
from agenttaint_benchmark.loader import load_scenarios
from agenttaint_benchmark.metrics import aggregate
from agenttaint_benchmark.report import latest_symlink, write_report
from agenttaint_benchmark.runner import run_scenario
from agenttaint_benchmark.schema import BenchmarkReport, DefenseMode, Split

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REPORTS = ROOT / "benchmarks" / "reports"

LIMITATIONS = [
    "Custom synthetic scenarios — not a substitute for production agent telemetry.",
    "No head-to-head numbers vs CaMeL/FIDES/CapLite/NeuroTaint (not run here).",
    "Semantic channel uses FixtureEmbeddingBackend for free/local reproducibility, "
    "not a production embedding model.",
    "CONFIRM is treated as non-success for ASR and non-completion for utility "
    "(no human in the loop during the batch run).",
    "Static recipient denylists are disabled in provenance baselines to isolate "
    "provenance mechanisms.",
    "Provenance P/R scored only for reconstruction-enabled defenses on attacks.",
    "AgentDojo / InjecAgent adapters are not included in this milestone run.",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agenttaint-benchmark")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run benchmark split and write reports")
    run.add_argument("--split", choices=[s.value for s in Split], default="test")
    run.add_argument("--seed", type=int, default=2120)
    run.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORTS,
        help="Report output directory",
    )
    run.add_argument(
        "--skip-ablations",
        action="store_true",
        help="Skip reconstruction channel ablations",
    )
    run.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override benchmarks/data directory",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd != "run":
        return 2

    split = Split(args.split)
    version, scenarios = load_scenarios(split, data_dir=args.data_dir)
    command = " ".join(["python -m agenttaint_benchmark", *sys.argv[1:]])

    usage_start = resource.getrusage(resource.RUSAGE_SELF)
    all_results = []
    per_defense = {}
    defenses = default_defense_matrix()
    for defense in defenses:
        rows = [run_scenario(sc, defense) for sc in scenarios]
        all_results.extend(rows)
        key = defense.mode.value
        if defense.mode == DefenseMode.RECONSTRUCTION_ONLY:
            key = f"{defense.mode.value}:{defense.ablation.value}"
        elif defense.mode == DefenseMode.COMBINED:
            key = f"{defense.mode.value}:{defense.ablation.value}"
        per_defense[key] = aggregate(rows)

    per_ablation = {}
    if not args.skip_ablations:
        for defense in ablation_matrix():
            rows = [run_scenario(sc, defense) for sc in scenarios]
            all_results.extend(rows)
            per_ablation[defense.ablation.value] = aggregate(rows)

    # Per-family breakdown for combined defense (held-out only).
    combined_cfg = next(
        d
        for d in defenses
        if d.mode == DefenseMode.COMBINED
    )
    combined_rows = [
        r
        for r in all_results
        if r.defense == DefenseMode.COMBINED.value
        and r.ablation == combined_cfg.ablation.value
    ]
    families = sorted({r.family for r in combined_rows})
    per_family = {
        fam: aggregate([r for r in combined_rows if r.family == fam]) for fam in families
    }

    # Challenge probes (excluded from held-out aggregates).
    challenge_results = []
    challenge_path = (args.data_dir or (ROOT / "benchmarks" / "data")) / (
        "scenarios_challenge.json"
    )
    if challenge_path.exists() and split == Split.TEST:
        _, challenge_scenarios = load_scenarios(
            Split.CHALLENGE, data_dir=args.data_dir
        )
        for defense in defenses:
            for sc in challenge_scenarios:
                challenge_results.append(run_scenario(sc, defense))

    usage_end = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = float(usage_end.ru_maxrss)
    # Linux ru_maxrss is kilobytes; macOS is bytes — document platform.
    cpu_user = float(usage_end.ru_utime - usage_start.ru_utime)

    # Attach resource stats to each aggregate (same process-level sample).
    for key, metrics in list(per_defense.items()):
        per_defense[key] = metrics.model_copy(
            update={"rss_kb_max": rss_kb, "cpu_user_s": cpu_user}
        )
    for key, metrics in list(per_ablation.items()):
        per_ablation[key] = metrics.model_copy(
            update={"rss_kb_max": rss_kb, "cpu_user_s": cpu_user}
        )

    report = BenchmarkReport(
        dataset_version=version,
        seed=args.seed,
        split=split.value,
        defenses=[d.mode.value for d in defenses],
        ablations=[d.ablation.value for d in ablation_matrix()]
        if not args.skip_ablations
        else [],
        command=command,
        config={
            "confirm_untrusted_influence": False,
            "fail_closed_unknown_high": False,
            "blocked_recipients": [],
            "semantic_backend": "FixtureEmbeddingBackend",
            "platform_rss_unit": "linux_kb_or_platform_ru_maxrss",
        },
        per_defense=per_defense,
        per_ablation=per_ablation,
        per_family_combined=per_family,
        challenge_results=challenge_results,
        results=all_results,
        limitations=LIMITATIONS
        + [
            "Challenge probes are excluded from held-out ASR/utility aggregates.",
            "Near-perfect held-out ASR on this small synthetic set does not imply "
            "real-world effectiveness; several attacks remain structurally easy.",
        ],
        notes=[
            "Held-out test split must not be used to tune thresholds.",
            f"Scenarios evaluated: {len(scenarios)}",
            f"Challenge probes evaluated: {len(challenge_results)}",
            "KNOWN/INFERRED/UNKNOWN distinctions preserved in evidence statuses.",
        ],
    )
    json_path, md_path = write_report(report, args.out)
    latest_symlink(json_path, f"latest_{split.value}.json")
    latest_symlink(md_path, f"latest_{split.value}.md")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(metrics_summary(per_defense))
    return 0


def metrics_summary(per_defense: dict) -> str:
    from agenttaint_benchmark.report import metrics_table

    return metrics_table(per_defense)


if __name__ == "__main__":
    raise SystemExit(main())
