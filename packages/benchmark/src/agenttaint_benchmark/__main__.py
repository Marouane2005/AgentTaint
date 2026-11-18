"""CLI: python -m agenttaint_benchmark run|experiment ..."""

from __future__ import annotations

import argparse
import json
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
from agenttaint_benchmark.runner import resolve_embedding_backend, run_scenario
from agenttaint_benchmark.schema import (
    BenchmarkReport,
    DefenseMode,
    SeedAggregate,
    Split,
)
from agenttaint_benchmark.variability import bootstrap_sample, summarize_variability

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REPORTS = ROOT / "benchmarks" / "reports"

LIMITATIONS = [
    "Custom synthetic scenarios — not a substitute for production agent telemetry.",
    "No head-to-head numbers vs CaMeL/FIDES/CapLite/NeuroTaint (not run here).",
    "CONFIRM is treated as non-success for ASR and non-completion for utility "
    "(no human in the loop during the batch run).",
    "Static recipient denylists are disabled in provenance baselines to isolate "
    "provenance mechanisms.",
    "Provenance P/R scored only for reconstruction-enabled defenses on attacks.",
    "Multi-seed variability uses bootstrap resampling of a fixed held-out corpus "
    "(evaluation is otherwise deterministic).",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agenttaint-benchmark")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--split", choices=[s.value for s in Split], default="test")
        sp.add_argument("--seed", type=int, default=2120)
        sp.add_argument("--out", type=Path, default=DEFAULT_REPORTS)
        sp.add_argument("--skip-ablations", action="store_true")
        sp.add_argument("--data-dir", type=Path, default=None)
        sp.add_argument(
            "--semantic-backend",
            default="fixture",
            help="fixture | bge | none",
        )
        sp.add_argument(
            "--tag",
            default="",
            help="Optional report filename tag (e.g. bge, fixture)",
        )

    run = sub.add_parser("run", help="Run benchmark split and write reports")
    add_common(run)

    exp = sub.add_parser(
        "experiment",
        help="Multi-seed bootstrap variability on a held-out split",
    )
    add_common(exp)
    exp.add_argument(
        "--seeds",
        default="2120,7,42,99,12345",
        help="Comma-separated seeds for bootstrap resampling",
    )
    return p


def _defense_key(defense) -> str:  # type: ignore[no-untyped-def]
    if defense.mode in {DefenseMode.RECONSTRUCTION_ONLY, DefenseMode.COMBINED}:
        return f"{defense.mode.value}:{defense.ablation.value}"
    return defense.mode.value


def _run_matrix(
    scenarios,
    *,
    skip_ablations: bool,
    embedding_backend,
    include_challenge: bool,
    data_dir: Path | None,
):
    all_results = []
    per_defense = {}
    defenses = default_defense_matrix()
    for defense in defenses:
        rows = [run_scenario(sc, defense, embedding_backend=embedding_backend) for sc in scenarios]
        all_results.extend(rows)
        per_defense[_defense_key(defense)] = aggregate(rows)

    per_ablation = {}
    if not skip_ablations:
        for defense in ablation_matrix():
            rows = [
                run_scenario(sc, defense, embedding_backend=embedding_backend) for sc in scenarios
            ]
            all_results.extend(rows)
            per_ablation[defense.ablation.value] = aggregate(rows)

    combined_cfg = next(d for d in defenses if d.mode == DefenseMode.COMBINED)
    combined_rows = [
        r
        for r in all_results
        if r.defense == DefenseMode.COMBINED.value and r.ablation == combined_cfg.ablation.value
    ]
    per_family = {
        fam: aggregate([r for r in combined_rows if r.family == fam])
        for fam in sorted({r.family for r in combined_rows})
    }
    # difficulty comes from scenario metadata via result family only — attach from scenarios
    difficulty_map = {sc.scenario_id: sc.difficulty for sc in scenarios}
    for r in combined_rows:
        r.metadata["difficulty"] = difficulty_map.get(r.scenario_id, "standard")
    per_difficulty = {
        diff: aggregate([r for r in combined_rows if r.metadata.get("difficulty") == diff])
        for diff in sorted({difficulty_map.get(r.scenario_id, "standard") for r in combined_rows})
    }

    challenge_results = []
    challenge_path = (data_dir or (ROOT / "benchmarks" / "data")) / ("scenarios_challenge.json")
    if include_challenge and challenge_path.exists():
        _, challenge_scenarios = load_scenarios(Split.CHALLENGE, data_dir=data_dir)
        for defense in defenses:
            for sc in challenge_scenarios:
                challenge_results.append(
                    run_scenario(sc, defense, embedding_backend=embedding_backend)
                )

    return {
        "defenses": defenses,
        "all_results": all_results,
        "per_defense": per_defense,
        "per_ablation": per_ablation,
        "per_family": per_family,
        "per_difficulty": per_difficulty,
        "challenge_results": challenge_results,
    }


def _attach_resources(per: dict, rss_kb: float, cpu_user: float) -> dict:
    return {
        k: v.model_copy(update={"rss_kb_max": rss_kb, "cpu_user_s": cpu_user})
        for k, v in per.items()
    }


def cmd_run(args: argparse.Namespace) -> int:
    split = Split(args.split)
    version, scenarios = load_scenarios(split, data_dir=args.data_dir)
    backend_name = args.semantic_backend
    try:
        embedder = resolve_embedding_backend(backend_name)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    backend_label = (
        "none" if embedder is None else getattr(embedder, "model_name", type(embedder).__name__)
    )
    command = " ".join(["python -m agenttaint_benchmark", *sys.argv[1:]])

    usage_start = resource.getrusage(resource.RUSAGE_SELF)
    bundle = _run_matrix(
        scenarios,
        skip_ablations=args.skip_ablations,
        embedding_backend=embedder,
        include_challenge=(split == Split.TEST),
        data_dir=args.data_dir,
    )
    usage_end = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = float(usage_end.ru_maxrss)
    cpu_user = float(usage_end.ru_utime - usage_start.ru_utime)

    per_defense = _attach_resources(bundle["per_defense"], rss_kb, cpu_user)
    per_ablation = _attach_resources(bundle["per_ablation"], rss_kb, cpu_user)

    report = BenchmarkReport(
        dataset_version=version,
        seed=args.seed,
        split=split.value,
        defenses=[d.mode.value for d in bundle["defenses"]],
        ablations=[d.ablation.value for d in ablation_matrix()] if not args.skip_ablations else [],
        command=command,
        config={
            "confirm_untrusted_influence": False,
            "fail_closed_unknown_high": False,
            "blocked_recipients": [],
            "semantic_backend": backend_label,
            "semantic_backend_cli": backend_name,
            "platform_rss_unit": "linux_kb_or_platform_ru_maxrss",
        },
        per_defense=per_defense,
        per_ablation=per_ablation,
        per_family_combined=bundle["per_family"],
        per_difficulty_combined=bundle["per_difficulty"],
        challenge_results=bundle["challenge_results"],
        results=bundle["all_results"],
        limitations=LIMITATIONS
        + [
            f"Semantic backend for this run: {backend_label}",
            "Challenge probes are excluded from held-out ASR/utility aggregates.",
            "Expanded M7 hard cases still synthetic — not real-world effectiveness.",
        ],
        notes=[
            "Held-out test split must not be used to tune thresholds.",
            f"Scenarios evaluated: {len(scenarios)}",
            f"Challenge probes evaluated: {len(bundle['challenge_results'])}",
            "KNOWN/INFERRED/UNKNOWN distinctions preserved in evidence statuses.",
        ],
    )
    tag = args.tag or backend_name
    json_path, md_path = write_report(report, args.out, tag=tag)
    latest_symlink(json_path, f"latest_{split.value}_{tag}.json")
    latest_symlink(md_path, f"latest_{split.value}_{tag}.md")
    if tag == "fixture" or backend_name == "fixture":
        latest_symlink(json_path, f"latest_{split.value}.json")
        latest_symlink(md_path, f"latest_{split.value}.md")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    from agenttaint_benchmark.report import metrics_table

    print(metrics_table(per_defense))
    return 0


def cmd_experiment(args: argparse.Namespace) -> int:
    """Full evaluation once, then bootstrap aggregates across seeds."""
    split = Split(args.split)
    version, scenarios = load_scenarios(split, data_dir=args.data_dir)
    backend_name = args.semantic_backend
    embedder = resolve_embedding_backend(backend_name)
    backend_label = (
        "none" if embedder is None else getattr(embedder, "model_name", type(embedder).__name__)
    )
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    command = " ".join(["python -m agenttaint_benchmark", *sys.argv[1:]])

    usage_start = resource.getrusage(resource.RUSAGE_SELF)
    # Single full pass (deterministic given backend); bootstrap reuses rows.
    bundle = _run_matrix(
        scenarios,
        skip_ablations=args.skip_ablations,
        embedding_backend=embedder,
        include_challenge=False,
        data_dir=args.data_dir,
    )
    defense_keys = list(bundle["per_defense"].keys())
    seed_runs: list[SeedAggregate] = []
    for seed in seeds:
        sampled = bootstrap_sample(scenarios, seed=seed)
        sampled_ids = [s.scenario_id for s in sampled]
        per = {}
        for key in defense_keys:
            # Rebuild aggregate by filtering full results with replacement counts
            rows = []
            index = {
                r.scenario_id: r
                for r in bundle["all_results"]
                if (
                    f"{r.defense}:{r.ablation}" == key
                    if ":" in key
                    else r.defense == key and r.ablation in {"none", ""}
                )
            }
            for sid in sampled_ids:
                if sid in index:
                    rows.append(index[sid])
            per[key] = aggregate(rows)
        seed_runs.append(SeedAggregate(seed=seed, per_defense=per))

    variability = summarize_variability(seed_runs, defenses=defense_keys)
    usage_end = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = float(usage_end.ru_maxrss)
    cpu_user = float(usage_end.ru_utime - usage_start.ru_utime)
    per_defense = _attach_resources(bundle["per_defense"], rss_kb, cpu_user)
    per_ablation = _attach_resources(bundle["per_ablation"], rss_kb, cpu_user)

    report = BenchmarkReport(
        dataset_version=version,
        seed=args.seed,
        split=split.value,
        defenses=[d.mode.value for d in bundle["defenses"]],
        ablations=[d.ablation.value for d in ablation_matrix()] if not args.skip_ablations else [],
        command=command,
        config={
            "mode": "multi_seed_bootstrap",
            "seeds": seeds,
            "semantic_backend": backend_label,
            "semantic_backend_cli": backend_name,
            "bootstrap": "resample_with_replacement_full_corpus_length",
        },
        per_defense=per_defense,
        per_ablation=per_ablation,
        per_family_combined=bundle["per_family"],
        per_difficulty_combined=bundle["per_difficulty"],
        seed_runs=seed_runs,
        variability=variability,
        results=bundle["all_results"],
        limitations=LIMITATIONS
        + [
            f"Semantic backend for this experiment: {backend_label}",
            "Bootstrap variability reflects sampling uncertainty on a fixed synthetic "
            "corpus, not stochastic model noise.",
        ],
        notes=[
            f"Full-corpus scenarios: {len(scenarios)}",
            f"Bootstrap seeds: {seeds}",
        ],
    )
    tag = args.tag or f"experiment_{backend_name}"
    json_path, md_path = write_report(report, args.out, tag=tag)
    latest_symlink(json_path, f"latest_experiment_{backend_name}.json")
    latest_symlink(md_path, f"latest_experiment_{backend_name}.md")
    # Also dump variability CSV-ish JSON for docs.
    var_path = args.out / f"variability_{backend_name}.json"
    var_path.write_text(
        json.dumps([v.model_dump() for v in variability], indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"wrote {var_path}")
    from agenttaint_benchmark.report import metrics_table, variability_table

    print(metrics_table(per_defense))
    print(variability_table(variability))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "experiment":
        return cmd_experiment(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
