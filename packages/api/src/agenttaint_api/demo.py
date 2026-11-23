"""Public demo mode: read-only console, runnable synthetic scenarios.

Enabled with ``AGENTTAINT_DEMO_MODE=1``. Every tool is a mock (no shell, no
network, no Docker); approvals and session resets are disabled; requests are
rate-limited. Scenario runs go through the real gateway and Cedar policy.
"""

from __future__ import annotations

import os
import re
import threading
from functools import lru_cache
from itertools import count
from typing import Any

from agenttaint_api import state as state_mod

MAX_TRACES = 200
_LOCK = threading.Lock()
_RUN_IDS = count(1)


def demo_mode() -> bool:
    return os.environ.get("AGENTTAINT_DEMO_MODE", "").strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def _scenarios() -> dict[str, Any]:
    """Curated catalogue: one scenario per family plus reconstruction/challenge cases."""
    from agenttaint_benchmark.loader import load_scenarios

    picked: dict[str, Any] = {}
    seen: set[tuple[str, str]] = set()
    _, test = load_scenarios("test")
    for sc in test:
        key = (sc.kind.value, sc.family.value)
        if key not in seen:
            seen.add(key)
            picked[sc.scenario_id] = sc
    _, rec = load_scenarios("reconstruction")
    for kind in ("attack", "benign"):
        sc = next(s for s in rec if s.kind.value == kind)
        picked[sc.scenario_id] = sc
    _, challenge = load_scenarios("challenge")
    for sc in challenge:
        picked[sc.scenario_id] = sc
    return picked


def catalog() -> list[dict[str, Any]]:
    out = []
    for sc in _scenarios().values():
        out.append(
            {
                "scenario_id": sc.scenario_id,
                "kind": sc.kind.value,
                "family": sc.family.value,
                "split": sc.split.value,
                "description": sc.description,
                "difficulty": sc.difficulty,
                "send_to": sc.send_to,
            }
        )
    out.sort(key=lambda d: (d["kind"] != "attack", d["split"], d["family"]))
    return out


def _defenses() -> tuple[Any, Any]:
    from agenttaint_benchmark.defenses import DefenseConfig
    from agenttaint_benchmark.schema import AblationModeName, DefenseMode

    return (
        DefenseConfig(DefenseMode.UNDEFENDED, AblationModeName.NONE),
        DefenseConfig(DefenseMode.COMBINED, AblationModeName.COMBINED),
    )


EXPLANATIONS: dict[str, str] = {
    "allow-low-medium": (
        "The agent made no high-risk call (nothing was sent), so AgentTaint let it through."
    ),
    "allow-medium": (
        "The agent made no high-risk call (nothing was sent), so AgentTaint let it through."
    ),
    "allow-low": (
        "The agent made no high-risk call (nothing was sent), so AgentTaint let it through."
    ),
    "allow-user-authorized-authority": (
        "The recipient came from your own instruction, so you authorized it. "
        "Untrusted text may mention it too, but it does not decide where data goes."
    ),
    "allow-high-authorized": (
        "The recipient came from your own instruction, so you authorized it. "
        "Untrusted text may mention it too, but it does not decide where data goes."
    ),
    "allow-medium-authorized": (
        "The recipient came from your own instruction, so you authorized it. "
        "Untrusted text may mention it too, but it does not decide where data goes."
    ),
    "allow-default": "No policy objected to this call.",
    "block-untrusted-influence": (
        "The recipient was taken from untrusted content (the email body), not from you. "
        "Letting outside text choose where your data goes is how prompt injection "
        "exfiltrates data, so the send was blocked."
    ),
    "block-inferred-untrusted-influence": (
        "No lineage was declared, but AgentTaint matched the recipient back to the "
        "untrusted content and blocked the send."
    ),
    "block-unknown-high-risk": (
        "A high-risk send had no provable source, so AgentTaint failed closed."
    ),
    "block-medium-untrusted-influence": (
        "A medium-risk call was driven by untrusted content and policy blocks it."
    ),
    "block-medium-undeclared-lineage": (
        "A medium-risk call had no declared lineage and policy blocks it."
    ),
    "confirm-high-risk": (
        "This send is high risk and its recipient was not clearly authorized by you, "
        "so a person must approve it first."
    ),
    "confirm-untrusted-influence": (
        "Untrusted content influenced this call. A person must approve it first."
    ),
    "confirm-inferred-untrusted-influence": (
        "AgentTaint found likely untrusted influence. A person must approve it first."
    ),
    "confirm-unknown-high-risk": (
        "This high-risk send has no provable source. A person must approve it first."
    ),
    "confirm-medium-untrusted-influence": (
        "A medium-risk call was influenced by untrusted content; it is held for approval."
    ),
    "confirm-medium-undeclared-lineage": (
        "A medium-risk call had no declared lineage; it is held for approval."
    ),
    "confirm-medium-inferred-untrusted": (
        "A medium-risk call looks influenced by untrusted content; it is held for approval."
    ),
}

VERDICT_HINT = {
    "ALLOW": "The call runs.",
    "CONFIRM": "The call is held until a person approves it (approvals are off in this demo).",
    "BLOCK": "The call never reaches the tool.",
}


def explain(decision: str, policy_id: str | None) -> str:
    base = EXPLANATIONS.get(policy_id or "", "")
    return f"{base} {VERDICT_HINT.get(decision, '')}".strip()


def _agent_call(scenario: Any) -> dict[str, Any] | None:
    if not scenario.send_to:
        return None
    return {
        "tool": "email.send",
        "arguments": {
            "to": scenario.send_to,
            "subject": scenario.send_subject,
            "body": scenario.send_body,
        },
    }


def _run_pair(scenario: Any, trace_label: str, scenario_info: dict[str, Any]) -> dict[str, Any]:
    from agenttaint_benchmark.runner import run_scenario

    undefended_cfg, combined_cfg = _defenses()
    baseline = run_scenario(scenario, undefended_cfg)
    with _LOCK:
        current = state_mod.get_state()
        if len(current.traces) >= MAX_TRACES:
            state_mod.seed_demo_session()
            current = state_mod.get_state()
        trace_id = f"{trace_label}#run{next(_RUN_IDS)}"
        result, trace = state_mod.replay_scenario(
            current, scenario, combined_cfg, None, source="visitor_run", trace_id=trace_id
        )
        current.session.notes = [*current.session.notes[-4:], f"Visitor ran {trace_label}."]
        graph = _run_graph(current, trace)
    return {
        "graph": graph,
        "scenario": scenario_info,
        "trace_id": trace["trace_id"],
        "call_ids": trace["call_ids"],
        "span_ids": trace["span_ids"],
        "agent_call": _agent_call(scenario),
        "without_agenttaint": {
            "decision": baseline.decision,
            "attack_success": baseline.attack_success,
            "benign_completed": baseline.benign_completed,
        },
        "with_agenttaint": {
            "decision": result.decision,
            "policy_id": result.policy_id,
            "attack_success": result.attack_success,
            "benign_completed": result.benign_completed,
            "evidence_statuses": result.evidence_statuses,
            "latency_ms": round(result.latency_ms, 2),
            "explanation": explain(result.decision, result.policy_id),
        },
    }


def _run_graph(current: Any, trace: dict[str, Any]) -> dict[str, Any]:
    """Spans, edges and decisions of one run, so the page can draw its graph directly."""
    span_ids = set(trace["span_ids"])
    full = state_mod.export_graph(current)
    nodes = [n for n in full["nodes"] if n["id"] in span_ids]
    edges = [e for e in full["edges"] if e["source"] in span_ids and e["target"] in span_ids]
    decisions = []
    for call_id in trace["call_ids"]:
        record = current.audit.get(call_id)
        if record is not None:
            decisions.append(record.model_dump(mode="json"))
    return {"nodes": nodes, "edges": edges, "decisions": decisions}


def run(scenario_id: str) -> dict[str, Any]:
    """Run one scenario undefended (throwaway stores) and with AgentTaint (shared)."""
    scenario = _scenarios().get(scenario_id)
    if scenario is None:
        raise KeyError(scenario_id)
    info = next(c for c in catalog() if c["scenario_id"] == scenario_id)
    return _run_pair(scenario, scenario.scenario_id, info)


# --- Free-text runs ------------------------------------------------------------

MAX_INSTRUCTION = 500
MAX_CONTENT = 2000
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
_SEND_WORDS = re.compile(
    r"\b(send|forward|e-?mail|cc|bcc|reply|share|transfer|mail|contact|notify)\b", re.I
)


def mock_agent(instruction: str, content: str) -> tuple[str | None, str]:
    """A deliberately obedient mock agent: it follows instructions wherever it reads them.

    This is the worst case AgentTaint is built for. Returns (recipient, reason).
    """
    user_addrs = _EMAIL.findall(instruction)
    content_addrs = _EMAIL.findall(content)
    if content_addrs and _SEND_WORDS.search(content):
        return content_addrs[-1], "followed an instruction found in the untrusted content"
    if user_addrs and _SEND_WORDS.search(instruction):
        return user_addrs[0], "used the address from your instruction"
    if content_addrs and _SEND_WORDS.search(instruction):
        return content_addrs[0], "replied to an address it found in the untrusted content"
    if user_addrs:
        return user_addrs[0], "used the address from your instruction"
    return None, "found nothing to send, so it only read the content"


def run_custom(instruction: str, content: str) -> dict[str, Any]:
    """Run visitor text through the real gateway with mocked email tools only."""
    from agenttaint_benchmark.schema import (
        PipelineOp,
        PipelineStep,
        Scenario,
        ScenarioFamily,
        ScenarioKind,
        Split,
    )

    instruction = instruction.strip()[:MAX_INSTRUCTION]
    content = content.strip()[:MAX_CONTENT]
    recipient, reason = mock_agent(instruction, content)
    user_addrs = _EMAIL.findall(instruction)
    from_content = recipient is not None and recipient not in user_addrs
    steps = [PipelineStep(op=PipelineOp.USER_INSTRUCTION, text=instruction)]
    if content:
        steps.append(PipelineStep(op=PipelineOp.READ_UNTRUSTED, text=content))
    steps.append(PipelineStep(op=PipelineOp.SEND if recipient else PipelineOp.READ_ONLY))
    summary = " ".join(content.split())[:160] or instruction[:160]
    scenario = Scenario(
        scenario_id="custom",
        split=Split.CHALLENGE,
        kind=ScenarioKind.ATTACK if from_content else ScenarioKind.BENIGN,
        family=ScenarioFamily.DIRECT,
        description="Your own text",
        pipeline=steps,
        send_to=recipient,
        send_subject="Re: your request",
        send_body=f"Summary: {summary}",
        # The proxy records the span a value was read from as its parent.
        argument_parent_mode="last" if from_content else "user",
        user_authorized_values=user_addrs,
        gold_untrusted_influences_recipient=from_content,
        gold_user_authorizes_recipient=recipient in user_addrs if recipient else False,
    )
    info = {
        "scenario_id": "custom",
        "kind": "custom",
        "family": "free_text",
        "split": "visitor",
        "description": "Your own instruction and content",
        "difficulty": "custom",
        "send_to": recipient,
    }
    out = _run_pair(scenario, "custom", info)
    out["agent_reason"] = reason
    return out


def seed_if_empty() -> None:
    with _LOCK:
        if state_mod.get_state().session.mode == "empty":
            state_mod.seed_demo_session()
