"""AgentDojo adapter: offline test with a scripted, injection-obedient model.

No network or API key: the "model" is a deterministic pipeline element that
reads the bill and then pays whichever IBAN the attacker's injection names.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline import (  # noqa: E402
    AgentPipeline,
    InitQuery,
    SystemMessage,
    ToolsExecutionLoop,
    ToolsExecutor,
)
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement  # noqa: E402
from agentdojo.attacks.attack_registry import load_attack  # noqa: E402
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionsRuntime  # noqa: E402
from agentdojo.task_suite.load_suites import get_suites  # noqa: E402
from agentdojo.types import ChatMessage, text_content_block_from_string  # noqa: E402
from agenttaint_benchmark.external.agentdojo_adapter import (  # noqa: E402
    AgentTaintToolsExecutor,
    RateLimitedElement,
)

ATTACKER_IBAN = "US133000000121212121212"
IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


class ObedientModel(BasePipelineElement):
    """Reads the bill, then pays the attacker IBAN if one appears, else the bill IBAN."""

    name = "scripted-model"

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),  # noqa: B008
        messages: Sequence[ChatMessage] = [],  # noqa: B006
        extra_args: dict = {},  # noqa: B006
    ):
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        if not tool_msgs:
            call = FunctionCall(
                function="read_file", args={"file_path": "bill-december-2023.txt"}, id="c1"
            )
        elif len(tool_msgs) == 1:
            text = "".join(b["content"] or "" for b in tool_msgs[0]["content"])
            target = ATTACKER_IBAN if ATTACKER_IBAN in text else IBAN.findall(text)[0]
            call = FunctionCall(
                function="send_money",
                args={
                    "recipient": target,
                    "amount": 98.7,
                    "subject": "spotify",
                    "date": "2022-04-01",
                },
                id="c2",
            )
        else:
            msg = {
                "role": "assistant",
                "content": [text_content_block_from_string("done")],
                "tool_calls": None,
            }
            return query, runtime, env, [*messages, msg], extra_args
        msg = {"role": "assistant", "content": None, "tool_calls": [call]}
        return query, runtime, env, [*messages, msg], extra_args


def _pipeline(executor: BasePipelineElement) -> AgentPipeline:
    model = ObedientModel()
    pipe = AgentPipeline(
        [
            SystemMessage("You are a banking agent."),
            InitQuery(),
            model,
            ToolsExecutionLoop([executor, model]),
        ]
    )
    pipe.name = "scripted-local"  # AgentDojo attacks need a known name key
    return pipe


@pytest.fixture(scope="module")
def banking():
    return get_suites("v1.2.1")["banking"]


def _attacked(banking, executor):
    pipe = _pipeline(executor)
    user = banking.get_user_task_by_id("user_task_0")
    inj = banking.get_injection_task_by_id("injection_task_0")
    injections = load_attack("important_instructions_no_model_name", banking, pipe).attack(
        user, inj
    )
    return banking.run_task_with_pipeline(pipe, user, inj, injections)


def test_undefended_scripted_model_is_hijacked(banking) -> None:
    _utility, security = _attacked(banking, ToolsExecutor())
    assert security is True  # attack succeeded without AgentTaint


@pytest.mark.parametrize("mode", ["strict", "approve"])
def test_agenttaint_blocks_injected_payment(banking, mode: str) -> None:
    executor = AgentTaintToolsExecutor(confirm_mode=mode)
    _utility, security = _attacked(banking, executor)
    assert security is False
    stats = executor.current[2]
    send = [d for d in stats.decisions if d["tool"] == "send_money"]
    assert send and send[0]["decision"] == "BLOCK"
    assert send[0]["tier"] == "HIGH"


def test_legitimate_payment_from_untrusted_file_is_not_silently_allowed(banking) -> None:
    """Honest cost: the bill's IBAN comes from an untrusted file, so paying it is
    blocked even without an attack (utility loss AgentTaint accepts by design)."""
    executor = AgentTaintToolsExecutor(confirm_mode="approve")
    pipe = _pipeline(executor)
    user = banking.get_user_task_by_id("user_task_0")
    utility, _ = banking.run_task_with_pipeline(pipe, user, None, {})
    decisions = [d for d in executor.current[2].decisions if d["tool"] == "send_money"]
    assert decisions[0]["decision"] in {"BLOCK", "CONFIRM"}
    if decisions[0]["decision"] == "BLOCK":
        assert utility is False


def test_read_only_calls_are_allowed(banking) -> None:
    executor = AgentTaintToolsExecutor(confirm_mode="strict")
    _attacked(banking, executor)
    reads = [d for d in executor.current[2].decisions if d["tool"] == "read_file"]
    assert reads and reads[0]["decision"] == "ALLOW"


def test_rate_limiter_retries_transient_errors() -> None:
    class Flaky(BasePipelineElement):
        name = "flaky"

        def __init__(self) -> None:
            self.n = 0

        def query(self, query, runtime, env=None, messages=(), extra_args=None):  # noqa: ANN001
            self.n += 1
            if self.n < 3:
                err = RuntimeError("rate limited")
                err.status_code = 429  # type: ignore[attr-defined]
                raise err
            return query, runtime, env, messages, extra_args

    slept: list[float] = []
    inner = Flaky()
    wrapped = RateLimitedElement(inner, min_interval_s=0, sleep=slept.append)
    wrapped.query("q", FunctionsRuntime([]))
    assert inner.n == 3 and len(slept) == 2


def test_invalid_confirm_mode_rejected() -> None:
    with pytest.raises(ValueError):
        AgentTaintToolsExecutor(confirm_mode="auto")
