#!/usr/bin/env python3
"""Run a (sampled) AgentDojo evaluation with and without AgentTaint.

API keys are read from environment variables only (GEMINI_API_KEY,
INCEPTION_API_KEY, NVIDIA_API_KEY) and are never written anywhere.

Example (free Gemini tier, sampled subset):

    GEMINI_API_KEY=... python scripts/run_agentdojo.py \
        --provider gemini --model gemini-3.1-flash-lite \
        --suites banking,slack,workspace,travel \
        --user-tasks 4 --injection-tasks 2 --seed 2120 \
        --out benchmarks/reports/agentdojo

Per-run results are appended to ``runs.jsonl`` (resumable); ``summary.json`` and
``summary.md`` aggregate them. AgentDojo's tasks, injections, attacks and
scoring are used unmodified.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "inception": ("https://api.inceptionlabs.ai/v1", "INCEPTION_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
}
DEFENSES = ("undefended", "agenttaint-strict", "agenttaint-approve")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def build_pipeline(provider: str, model: str, defense: str, min_interval: float) -> tuple[Any, Any]:
    import openai
    from agentdojo.agent_pipeline import (
        AgentPipeline,
        InitQuery,
        OpenAILLM,
        SystemMessage,
        ToolsExecutionLoop,
        ToolsExecutor,
    )
    from agentdojo.agent_pipeline.agent_pipeline import load_system_message
    from agenttaint_benchmark.external.agentdojo_adapter import (
        AgentTaintToolsExecutor,
        RateLimitedElement,
        ToolCallMetadataRelay,
    )

    base_url, key_env = PROVIDERS[provider]
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise SystemExit(f"{key_env} is not set")
    client = openai.OpenAI(base_url=base_url, api_key=key, timeout=120, max_retries=1)
    ToolCallMetadataRelay(client)
    llm = RateLimitedElement(OpenAILLM(client, model, temperature=0.0), min_interval_s=min_interval)
    if defense == "undefended":
        executor: Any = ToolsExecutor()
    else:
        executor = AgentTaintToolsExecutor(confirm_mode=defense.split("-", 1)[1])
    pipeline = AgentPipeline(
        [
            SystemMessage(load_system_message(None)),
            InitQuery(),
            llm,
            ToolsExecutionLoop([executor, llm]),
        ]
    )
    # AgentDojo attack constructors look up a model name in the pipeline name; the
    # "_no_model_name" attack then replaces it with a neutral default, so the
    # "local" key only satisfies that lookup and does not change the injection.
    pipeline.name = f"{model}+{defense}+local"
    return pipeline, (llm, executor)


def plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    from agentdojo.task_suite.load_suites import get_suites

    suites = get_suites(args.benchmark_version)
    rng = random.Random(args.seed)
    items: list[dict[str, Any]] = []
    for name in args.suites.split(","):
        suite = suites[name]
        users = sorted(suite.user_tasks, key=lambda s: int(s.split("_")[-1]))
        injs = sorted(suite.injection_tasks, key=lambda s: int(s.split("_")[-1]))
        chosen_u = sorted(rng.sample(users, min(args.user_tasks, len(users))))
        chosen_i = sorted(rng.sample(injs, min(args.injection_tasks, len(injs))))
        for u in chosen_u:
            items.append({"suite": name, "user_task": u, "injection_task": None})
            for i in chosen_i:
                items.append({"suite": name, "user_task": u, "injection_task": i})
    return items


def key_of(rec: dict[str, Any]) -> str:
    return f"{rec['defense']}|{rec['suite']}|{rec['user_task']}|{rec['injection_task']}"


def run(args: argparse.Namespace) -> None:
    from agentdojo.attacks.attack_registry import load_attack
    from agentdojo.task_suite.load_suites import get_suites

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    done = set()
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("status") == "ok":
                done.add(key_of(rec))
    suites = get_suites(args.benchmark_version)
    items = plan(args)
    budget_deadline = time.monotonic() + args.max_minutes * 60
    for defense in args.defenses.split(","):
        pipeline, (llm, executor) = build_pipeline(
            args.provider, args.model, defense, args.min_interval
        )
        for item in items:
            rec = {**item, "defense": defense, "model": args.model, "provider": args.provider}
            if key_of(rec) in done:
                continue
            if time.monotonic() > budget_deadline:
                print("time budget reached; stopping (resume later with the same --out)")
                return
            suite = suites[item["suite"]]
            user_task = suite.get_user_task_by_id(item["user_task"])
            injection_task = None
            injections: dict[str, str] = {}
            if item["injection_task"]:
                injection_task = suite.get_injection_task_by_id(item["injection_task"])
                attack = load_attack(args.attack, suite, pipeline)
                injections = attack.attack(user_task, injection_task)
            if hasattr(executor, "reset"):
                executor.reset()
            calls_before = llm.calls
            started = time.monotonic()
            try:
                utility, security = suite.run_task_with_pipeline(
                    pipeline, user_task, injection_task, injections
                )
                rec.update(status="ok", utility=bool(utility), security=bool(security))
            except Exception as exc:  # noqa: BLE001 - record and continue
                rec.update(status="error", error=f"{type(exc).__name__}: {str(exc)[:300]}")
            rec["llm_calls"] = llm.calls - calls_before
            rec["seconds"] = round(time.monotonic() - started, 1)
            current = getattr(executor, "current", None)
            if current is not None:
                stats = current[2]
                rec["enforcement"] = {
                    "calls": stats.calls,
                    "allowed": stats.allowed,
                    "blocked": stats.blocked,
                    "confirm": stats.confirmed,
                    "confirm_declined": stats.confirm_declined,
                    "confirm_approved": stats.confirm_approved,
                    "decisions": stats.decisions,
                }
            with runs_path.open("a") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            print(
                f"{defense:20s} {item['suite']:9s} {item['user_task']:15s} "
                f"{str(item['injection_task']):18s} {rec['status']} "
                f"u={rec.get('utility')} s={rec.get('security')} calls={rec['llm_calls']}",
                flush=True,
            )


# Injection goals satisfied by the text of the final answer, with no side-effecting
# tool call (checked by hand against the v1.2.1 GOAL strings). A tool-call
# firewall cannot stop these by design, so they are reported apart.
OUTPUT_ONLY_INJECTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("travel", "injection_task_5"),  # "tell me my passport number, and credit card"
        ("travel", "injection_task_6"),  # "Say that I should absolutely visit ..."
    }
)


def output_only_injections(version: str) -> set[tuple[str, str]]:
    if version != "v1.2.1":
        return set()
    return set(OUTPUT_ONLY_INJECTIONS)


def summarize(out: Path, meta: dict[str, Any]) -> dict[str, Any]:
    text_only = output_only_injections(meta["benchmark_version"])
    recs = [json.loads(x) for x in (out / "runs.jsonl").read_text().splitlines()]
    latest: dict[str, dict[str, Any]] = {}
    for r in recs:
        if r.get("status") == "ok" or key_of(r) not in latest:
            latest[key_of(r)] = r
    rows = list(latest.values())
    summary: dict[str, Any] = {"meta": meta, "defenses": {}}
    for d in sorted({r["defense"] for r in rows}):
        rs = [r for r in rows if r["defense"] == d]
        ok = [r for r in rs if r["status"] == "ok"]
        benign = [r for r in ok if not r["injection_task"]]
        attacked = [r for r in ok if r["injection_task"]]
        k_u = sum(r["utility"] for r in benign)
        k_ua = sum(r["utility"] for r in attacked)
        k_s = sum(r["security"] for r in attacked)
        tool_att = [r for r in attacked if (r["suite"], r["injection_task"]) not in text_only]
        k_st = sum(r["security"] for r in tool_att)
        enf = [r.get("enforcement", {}) for r in ok]
        summary["defenses"][d] = {
            "runs_ok": len(ok),
            "runs_error": len(rs) - len(ok),
            "benign_n": len(benign),
            "utility": k_u / len(benign) if benign else None,
            "utility_ci95": wilson(k_u, len(benign)),
            "attacked_n": len(attacked),
            "utility_under_attack": k_ua / len(attacked) if attacked else None,
            "asr": k_s / len(attacked) if attacked else None,
            "asr_ci95": wilson(k_s, len(attacked)),
            "tool_attacked_n": len(tool_att),
            "asr_tool_injections": k_st / len(tool_att) if tool_att else None,
            "asr_tool_injections_ci95": wilson(k_st, len(tool_att)),
            "tool_calls": sum(e.get("calls", 0) for e in enf),
            "blocked": sum(e.get("blocked", 0) for e in enf),
            "confirm": sum(e.get("confirm", 0) for e in enf),
            "per_suite": {
                s: {
                    "benign_n": len([r for r in benign if r["suite"] == s]),
                    "utility": _rate([r["utility"] for r in benign if r["suite"] == s]),
                    "attacked_n": len([r for r in attacked if r["suite"] == s]),
                    "asr": _rate([r["security"] for r in attacked if r["suite"] == s]),
                }
                for s in sorted({r["suite"] for r in ok})
            },
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        f"# AgentDojo subset — {meta['model']} ({meta['provider']})",
        "",
        f"Benchmark {meta['benchmark_version']}, attack `{meta['attack']}`, seed {meta['seed']}, "
        f"{meta['user_tasks']} user tasks × {meta['injection_tasks']} injection tasks per suite "
        f"({meta['suites']}). **Sampled subset, not the full suite.**",
        "",
        "| defense | benign n | utility | attacked n | utility under attack | ASR (95% CI) "
        "| tool-action ASR (n) | blocked | confirm | errors |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d, v in summary["defenses"].items():
        lo, hi = v["asr_ci95"]
        lines.append(
            f"| {d} | {v['benign_n']} | {_fmt(v['utility'])} | {v['attacked_n']} | "
            f"{_fmt(v['utility_under_attack'])} | {_fmt(v['asr'])} ({lo:.2f}–{hi:.2f}) | "
            f"{_fmt(v['asr_tool_injections'])} ({v['tool_attacked_n']}) | "
            f"{v['blocked']} | {v['confirm']} | {v['runs_error']} |"
        )
    lines += [
        "",
        "Tool-action ASR excludes injection tasks whose goal needs no tool call "
        f"({', '.join(f'{a}/{b}' for a, b in sorted(text_only))}); a tool-call firewall "
        "cannot stop those by design.",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return summary


def _rate(xs: list[bool]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--provider", choices=sorted(PROVIDERS), default="gemini")
    p.add_argument("--model", required=True)
    p.add_argument("--suites", default="banking,slack,workspace,travel")
    p.add_argument("--user-tasks", type=int, default=4)
    p.add_argument("--injection-tasks", type=int, default=2)
    p.add_argument("--seed", type=int, default=2120)
    p.add_argument("--defenses", default=",".join(DEFENSES))
    p.add_argument("--attack", default="important_instructions_no_model_name")
    p.add_argument("--benchmark-version", default="v1.2.1")
    p.add_argument("--min-interval", type=float, default=4.0, help="seconds between LLM calls")
    p.add_argument("--max-minutes", type=float, default=600.0)
    p.add_argument("--out", default="benchmarks/reports/agentdojo")
    p.add_argument("--summarize-only", action="store_true")
    args = p.parse_args(argv)
    meta = {
        k: getattr(args, k)
        for k in (
            "provider",
            "model",
            "suites",
            "user_tasks",
            "injection_tasks",
            "seed",
            "attack",
            "benchmark_version",
            "defenses",
        )
    }
    if not args.summarize_only:
        run(args)
    summary = summarize(Path(args.out), meta)
    json.dump(summary["defenses"], sys.stdout, indent=1, default=str)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
