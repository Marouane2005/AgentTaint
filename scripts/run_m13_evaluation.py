#!/usr/bin/env python3
"""Milestone 13 security & performance evaluation harness.

Reuses the custom benchmark matrix (defenses + channel ablations), records
process RSS/CPU, and writes a docs-facing markdown summary. Generated JSON
stays under benchmarks/reports/ (gitignored).
"""

from __future__ import annotations

import argparse
import resource
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agenttaint_benchmark.defenses import (  # noqa: E402
    DefenseConfig,  # noqa: E402
    ablation_matrix,
    default_defense_matrix,
)
from agenttaint_benchmark.loader import load_scenarios  # noqa: E402
from agenttaint_benchmark.metrics import aggregate  # noqa: E402
from agenttaint_benchmark.report import (  # noqa: E402
    latest_symlink,
    metrics_table,
    write_report,
)
from agenttaint_benchmark.runner import resolve_embedding_backend, run_scenario  # noqa: E402
from agenttaint_benchmark.schema import (  # noqa: E402
    AblationModeName,
    BenchmarkReport,
    DefenseMode,
    Split,
)

LIMITATIONS = [
    "Custom synthetic scenarios — not a substitute for production agent telemetry.",
    "No head-to-head numbers vs CaMeL/FIDES/CapLite/NeuroTaint (not run here).",
    "CONFIRM is treated as non-success for ASR and non-completion for utility "
    "(no human in the loop during the batch run).",
    "Static recipient denylists are disabled in provenance baselines to isolate "
    "provenance mechanisms.",
    "Provenance P/R scored only for reconstruction-enabled defenses on attacks.",
    "M13 microbench RSS is process peak (ru_maxrss), not per-call attribution.",
    "AgentDojo / InjecAgent ASR not evaluated (no LLM required for this run).",
]


def m13_ablation_matrix() -> list[DefenseConfig]:
    """Lexical / structural / semantic / lexical+structural / explicit channels."""
    modes = [
        AblationModeName.LEXICAL,
        AblationModeName.STRUCTURAL,
        AblationModeName.SEMANTIC,
        AblationModeName.LEXICAL_STRUCTURAL,
        AblationModeName.EXPLICIT,
    ]
    return [DefenseConfig(DefenseMode.RECONSTRUCTION_ONLY, ablation=m) for m in modes]


def main() -> int:
    parser = argparse.ArgumentParser(description="M13 security & performance evaluation")
    parser.add_argument("--split", default="test")
    parser.add_argument("--seed", type=int, default=2120)
    parser.add_argument("--tag", default="m13")
    parser.add_argument("--semantic-backend", default="fixture")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "benchmarks" / "reports",
    )
    args = parser.parse_args()

    version, scenarios = load_scenarios(Split(args.split))
    embedder = resolve_embedding_backend(args.semantic_backend)
    backend_label = (
        "none" if embedder is None else getattr(embedder, "model_name", type(embedder).__name__)
    )

    defenses = default_defense_matrix()
    ablations = m13_ablation_matrix()
    # Keep standard ablation_matrix coverage too (without duplicating explicit).
    for cfg in ablation_matrix():
        if cfg.ablation not in {a.ablation for a in ablations}:
            ablations.append(cfg)

    usage_start = resource.getrusage(resource.RUSAGE_SELF)
    wall_start = time.perf_counter()
    all_results = []
    per_defense: dict = {}
    for cfg in defenses:
        rows = [run_scenario(sc, cfg, embedding_backend=embedder) for sc in scenarios]
        all_results.extend(rows)
        key = (
            f"{cfg.mode.value}:{cfg.ablation.value}"
            if cfg.mode in {DefenseMode.RECONSTRUCTION_ONLY, DefenseMode.COMBINED}
            else cfg.mode.value
        )
        per_defense[key] = aggregate(rows)

    per_ablation: dict = {}
    for cfg in ablations:
        rows = [run_scenario(sc, cfg, embedding_backend=embedder) for sc in scenarios]
        all_results.extend(rows)
        per_ablation[cfg.ablation.value] = aggregate(rows)

    # Combined per-family / difficulty
    combined_rows = [
        r
        for r in all_results
        if r.defense == DefenseMode.COMBINED.value and r.ablation == "combined"
    ]
    difficulty_map = {sc.scenario_id: sc.difficulty for sc in scenarios}
    for r in combined_rows:
        r.metadata["difficulty"] = difficulty_map.get(r.scenario_id, "standard")
    per_family = {
        fam: aggregate([r for r in combined_rows if r.family == fam])
        for fam in sorted({r.family for r in combined_rows})
    }
    per_difficulty = {
        diff: aggregate([r for r in combined_rows if r.metadata.get("difficulty") == diff])
        for diff in sorted({difficulty_map.get(r.scenario_id, "standard") for r in combined_rows})
    }

    # Challenge probes
    challenge_results = []
    _, challenge_scenarios = load_scenarios(Split.CHALLENGE)
    for cfg in defenses:
        for sc in challenge_scenarios:
            challenge_results.append(run_scenario(sc, cfg, embedding_backend=embedder))

    wall_s = time.perf_counter() - wall_start
    usage_end = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = float(usage_end.ru_maxrss)
    cpu_user = float(usage_end.ru_utime - usage_start.ru_utime)

    def attach(d: dict) -> dict:
        return {
            k: v.model_copy(update={"rss_kb_max": rss_kb, "cpu_user_s": cpu_user})
            for k, v in d.items()
        }

    per_defense = attach(per_defense)
    per_ablation = attach(per_ablation)

    command = (
        f"python scripts/run_m13_evaluation.py --split {args.split} "
        f"--seed {args.seed} --semantic-backend {args.semantic_backend} --tag {args.tag}"
    )
    report = BenchmarkReport(
        dataset_version=version,
        seed=args.seed,
        split=args.split,
        defenses=[d.mode.value for d in defenses],
        ablations=[a.ablation.value for a in ablations],
        command=command,
        config={
            "milestone": "m13",
            "semantic_backend": backend_label,
            "semantic_backend_cli": args.semantic_backend,
            "wall_clock_s": round(wall_s, 3),
            "platform_rss_unit": "linux_kb_or_platform_ru_maxrss",
        },
        per_defense=per_defense,
        per_ablation=per_ablation,
        per_family_combined=per_family,
        per_difficulty_combined=per_difficulty,
        challenge_results=challenge_results,
        results=all_results,
        limitations=LIMITATIONS
        + [
            f"Semantic backend for this run: {backend_label}",
            "Challenge probes excluded from held-out ASR/utility aggregates.",
            "Prior M7/M12 markdown reports preserved; this file is additive.",
        ],
        notes=[
            f"Scenarios evaluated: {len(scenarios)}",
            f"Challenge probes: {len(challenge_results)}",
            f"Wall clock seconds: {wall_s:.3f}",
            f"ru_maxrss_kb: {rss_kb}",
            f"cpu_user_s: {cpu_user:.3f}",
            f"Generated at: {datetime.now(UTC).isoformat()}",
            "Ablations: lexical, structural, semantic, lexical_structural, explicit "
            "(under reconstruction_only) plus primary combined defense.",
        ],
    )
    json_path, md_path = write_report(report, args.out, tag=args.tag)
    latest_symlink(json_path, f"latest_{args.split}_{args.tag}.json")
    latest_symlink(md_path, f"latest_{args.split}_{args.tag}.md")

    docs = ROOT / "docs" / "benchmark_results_m13.md"
    # Prepend M13 framing, then the generated tables.
    body = md_path.read_text(encoding="utf-8")
    framing = "\n".join(
        [
            "# Milestone 13 — Security & performance evaluation",
            "",
            "Additive report (does not overwrite M7/M12 result docs).",
            "",
            "## Scope",
            "",
            "- Held-out custom suite defenses + reconstruction channel ablations",
            "- Adversarial unit suite: `tests/unit/test_m13_adversarial_evaluation.py`",
            "- Cross-process MCP coverage remains in "
            "`tests/integration/test_m10_multiprocess_proxy.py`",
            "- Latency/memory from scenario runner + process `ru_maxrss` / CPU user",
            "",
            f"- **Wall clock:** `{wall_s:.3f}s`",
            f"- **ru_maxrss:** `{rss_kb}` (platform units; Linux = KiB)",
            f"- **CPU user:** `{cpu_user:.3f}s`",
            "",
            "## Measured tables",
            "",
        ]
    )
    docs.write_text(framing + body + "\n", encoding="utf-8")

    # Also keep a stable copy under reports for local browsing.
    stable = args.out / f"report_{args.split}_{args.tag}.md"
    shutil.copyfile(md_path, stable)

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"wrote {docs}")
    print(metrics_table(per_defense))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
