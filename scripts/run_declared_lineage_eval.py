#!/usr/bin/env python3
"""Does reconstruction still run when a caller declares lineage?

Compares the ``combined`` defense on a benchmark split under three corpus sources:

* ``candidates`` – the harness hands the scenario corpus to the gateway (default for
  ``python -m agenttaint_benchmark``).
* ``session``   – the gateway only knows what it labelled itself (how the MCP proxy runs).
* ``none``      – no corpus: emulates a gateway that skips reconstruction when lineage is
  declared (the behaviour before always-on session reconstruction).

For each arm it prints attack success (ALLOWed attacks), benign BLOCK and CONFIRM rates,
and lists scenarios whose decision differs from the ``candidates`` arm.

    python scripts/run_declared_lineage_eval.py --split test --semantic-backend fixture
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agenttaint_benchmark.defenses import DefenseConfig
from agenttaint_benchmark.loader import load_scenarios
from agenttaint_benchmark.runner import resolve_embedding_backend, run_scenario
from agenttaint_benchmark.schema import AblationModeName, DefenseMode

ARMS = ("candidates", "session", "none")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--split", default="test")
    parser.add_argument("--semantic-backend", default="fixture")
    parser.add_argument("--json", type=Path, help="Write the full comparison here")
    args = parser.parse_args()

    _version, scenarios = load_scenarios(args.split)
    embedder = resolve_embedding_backend(args.semantic_backend)
    defense = DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED)

    outcomes: dict[str, dict[str, tuple[str, str | None, str]]] = {a: {} for a in ARMS}
    for arm in ARMS:
        for sc in scenarios:
            res = run_scenario(sc, defense, embedding_backend=embedder, corpus_source=arm)
            outcomes[arm][sc.scenario_id] = (
                str(getattr(res.decision, "value", res.decision)),
                res.policy_id,
                str(getattr(res.kind, "value", res.kind)),
            )

    print(f"split={args.split} scenarios={len(scenarios)} defense=combined")
    print(
        f"{'arm':<11} {'atk':>4} {'ALLOW':>6} {'BLOCK':>6} {'CONF':>5} | "
        f"{'ben':>4} {'ALLOW':>6} {'BLOCK':>6} {'CONF':>5}"
    )
    summary: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        row = {
            "atk": 0,
            "atk_allow": 0,
            "atk_block": 0,
            "atk_confirm": 0,
            "ben": 0,
            "ben_allow": 0,
            "ben_block": 0,
            "ben_confirm": 0,
        }
        for decision, _policy, kind in outcomes[arm].values():
            pre = "atk" if kind == "attack" else "ben"
            row[pre] += 1
            row[f"{pre}_{decision.lower()}"] = row.get(f"{pre}_{decision.lower()}", 0) + 1
        summary[arm] = row
        print(
            f"{arm:<11} {row['atk']:>4} {row['atk_allow']:>6} {row['atk_block']:>6} "
            f"{row['atk_confirm']:>5} | {row['ben']:>4} {row['ben_allow']:>6} "
            f"{row['ben_block']:>6} {row['ben_confirm']:>5}"
        )

    flips = []
    for arm in ARMS[1:]:
        for sid, (decision, policy, kind) in outcomes[arm].items():
            base = outcomes["candidates"][sid]
            if decision != base[0]:
                flips.append((arm, sid, kind, base[0], decision, policy))
    print(f"\n{len(flips)} decision(s) differ from the 'candidates' arm")
    for arm, sid, kind, was, now, policy in flips:
        print(f"  [{arm}] {sid} ({kind}): {was} -> {now} ({policy})")
    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "flips": flips}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
