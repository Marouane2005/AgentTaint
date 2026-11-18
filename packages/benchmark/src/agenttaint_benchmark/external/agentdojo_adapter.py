"""Run AgentDojo task suites with AgentTaint enforcing every tool call.

The adapter replaces AgentDojo's ``ToolsExecutor`` with
``AgentTaintToolsExecutor``. Each tool call the model makes goes through a real
``SecurityGateway`` (risk tiering, provenance registry, reconstruction over the
session's untrusted spans, Cedar policy, confirmation service) before the
AgentDojo function runs. Nothing about AgentDojo's tasks, injections, attacks or
scoring is modified.

The model under test never declares provenance, so every call has undeclared
lineage; the gateway falls back to reconstruction over what the session has
actually seen. That is the hardest setting for AgentTaint.

CONFIRM handling (there is no human in a batch benchmark):

- ``strict``: CONFIRM is treated as "human declined"; the call does not run.
- ``approve``: CONFIRM is treated as "human approved"; the confirmation is
  approved out-of-band and the identical call is retried. Only BLOCK decisions
  stop calls. This brackets the effect of a real reviewer from above.
"""

from __future__ import annotations

import secrets
import time
from ast import literal_eval
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.tool_execution import is_string_list, tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionReturnType, FunctionsRuntime
from agentdojo.types import ChatMessage, ChatToolResultMessage, text_content_block_from_string
from agenttaint_core.schemas import DecisionOutcome
from agenttaint_mcp_proxy.backends import ToolSpec
from agenttaint_mcp_proxy.gateway import SecurityGateway
from agenttaint_mcp_proxy.server import build_gateway_from_paths

ROOT = Path(__file__).resolve().parents[5]
TRUST_REGISTRY = ROOT / "policies" / "agentdojo_trust_registry.yaml"
POLICY = ROOT / "policies" / "provenance_policy.yaml"
AGENT_ID = "agentdojo-agent"
CONFIRM_MODES = ("strict", "approve")

# Arguments that choose *who/where/what* an action affects.
AUTHORITY_ARGUMENTS = frozenset(
    {
        "recipients",
        "recipient",
        "cc",
        "bcc",
        "email",
        "user_email",
        "user",
        "participants",
        "channel",
        "iban",
        "url",
        "password",
        "amount",
        "file_id",
        "email_id",
        "event_id",
        "hotel",
        "company",
        "restaurant",
        "street",
        "city",
    }
)
# Arguments that carry payload text.
CONTENT_ARGUMENTS = frozenset({"body", "content", "subject", "description", "title"})


@dataclass
class _DojoBackend:
    """ToolBackend that executes AgentDojo functions in the task environment."""

    runtime: FunctionsRuntime | None = None
    env: Env | None = None
    formatter: Callable[[FunctionReturnType], str] = tool_result_to_str
    last_error: str | None = None

    def list_tools(self) -> list[ToolSpec]:
        if self.runtime is None:
            return []
        return [
            ToolSpec(name=f.name, description=f.description, input_schema={})
            for f in self.runtime.functions.values()
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        assert self.runtime is not None and self.env is not None
        result, error = self.runtime.run_function(self.env, name, arguments)
        self.last_error = error
        return self.formatter(result)


@dataclass
class TaskStats:
    """Per-task enforcement counters (stored in ``extra_args``)."""

    calls: int = 0
    allowed: int = 0
    blocked: int = 0
    confirmed: int = 0
    confirm_declined: int = 0
    confirm_approved: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)


def new_gateway(backend: _DojoBackend) -> SecurityGateway:
    gateway = build_gateway_from_paths(
        backend=backend,
        trust_registry_path=TRUST_REGISTRY,
        policy_path=POLICY,
        confirmation_secret=secrets.token_hex(32),
    )
    gateway.authority_argument_names = set(AUTHORITY_ARGUMENTS)
    gateway.content_argument_names = set(CONTENT_ARGUMENTS)
    return gateway


class AgentTaintToolsExecutor(BasePipelineElement):
    """Drop-in replacement for AgentDojo's ToolsExecutor that enforces AgentTaint."""

    name = "agenttaint"

    def __init__(
        self,
        confirm_mode: str = "strict",
        tool_output_formatter: Callable[[FunctionReturnType], str] = tool_result_to_str,
    ) -> None:
        if confirm_mode not in CONFIRM_MODES:
            raise ValueError(f"confirm_mode must be one of {CONFIRM_MODES}")
        self.confirm_mode = confirm_mode
        self.output_formatter = tool_output_formatter
        self.reset()

    def reset(self) -> None:
        """Forget per-task state (call before each AgentDojo task)."""
        self.current: tuple[SecurityGateway, _DojoBackend, TaskStats] | None = None

    def _state(
        self, query: str, extra_args: dict
    ) -> tuple[SecurityGateway, _DojoBackend, TaskStats]:
        state = extra_args.get("agenttaint")
        if state is None:
            backend = _DojoBackend(formatter=self.output_formatter)
            gateway = new_gateway(backend)
            gateway.registry.record_user_instruction(content=query, agent_id=AGENT_ID)
            state = (gateway, backend, TaskStats())
            extra_args["agenttaint"] = state
            self.current = state
        return state

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),  # noqa: B008 - AgentDojo interface
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},  # noqa: B006 - AgentDojo interface
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if not messages or messages[-1]["role"] != "assistant":
            return query, runtime, env, messages, extra_args
        tool_calls = messages[-1]["tool_calls"]
        if not tool_calls:
            return query, runtime, env, messages, extra_args

        extra_args = dict(extra_args)
        gateway, backend, stats = self._state(query, extra_args)
        backend.runtime, backend.env = runtime, env
        known = {f.name for f in runtime.functions.values()}

        results: list[ChatToolResultMessage] = []
        for call in tool_calls:
            if call.function not in known:
                results.append(self._msg(call, "", f"Invalid tool {call.function} provided."))
                continue
            for key, value in call.args.items():
                if isinstance(value, str) and is_string_list(value):
                    call.args[key] = literal_eval(value)
            args = dict(call.args)
            text, error = self._enforce(gateway, backend, stats, call.function, args)
            results.append(self._msg(call, text, error))
        return query, runtime, env, [*messages, *results], extra_args

    def _enforce(
        self,
        gateway: SecurityGateway,
        backend: _DojoBackend,
        stats: TaskStats,
        tool: str,
        args: dict[str, Any],
    ) -> tuple[str, str | None]:
        stats.calls += 1
        backend.last_error = None
        outcome = gateway.invoke(tool, args, agent_id=AGENT_ID, raise_on_deny=False)
        decision = outcome.decision
        record = {
            "tool": tool,
            "tier": decision.risk_tier.value,
            "decision": decision.decision.value,
            "policy_id": decision.policy_id,
        }
        stats.decisions.append(record)
        if decision.decision == DecisionOutcome.ALLOW:
            stats.allowed += 1
            return str(outcome.result), backend.last_error
        if decision.decision == DecisionOutcome.BLOCK:
            stats.blocked += 1
            return "", (
                f"AgentTaint blocked this call ({decision.policy_id}): untrusted or "
                "unknown provenance cannot authorize this action."
            )
        stats.confirmed += 1
        cid = decision.confirmation_id
        if self.confirm_mode == "strict" or cid is None or gateway.confirmation is None:
            stats.confirm_declined += 1
            record["resolution"] = "declined"
            return "", (
                f"AgentTaint requires human confirmation for this call ({decision.policy_id}); "
                "the reviewer declined."
            )
        gateway.confirmation.approve(cid)  # type: ignore[attr-defined]
        retry = gateway.invoke(
            tool, args, agent_id=AGENT_ID, raise_on_deny=False, confirmation_id=cid
        )
        record["resolution"] = retry.decision.decision.value
        if retry.decision.decision == DecisionOutcome.ALLOW:
            stats.confirm_approved += 1
            return str(retry.result), backend.last_error
        stats.blocked += 1
        return "", f"AgentTaint blocked the confirmed retry ({retry.decision.policy_id})."

    @staticmethod
    def _msg(call: Any, text: str, error: str | None) -> ChatToolResultMessage:
        return ChatToolResultMessage(
            role="tool",
            content=[text_content_block_from_string(text)],
            tool_call_id=call.id,
            tool_call=call,
            error=error,
        )


class RateLimitedElement(BasePipelineElement):
    """Wraps an LLM element: spaces requests and backs off on 429/5xx."""

    def __init__(
        self,
        inner: BasePipelineElement,
        *,
        min_interval_s: float = 4.0,
        max_attempts: int = 8,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", None)
        self.min_interval_s = min_interval_s
        self.max_attempts = max_attempts
        self._sleep = sleep
        self._last = 0.0
        self.calls = 0

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),  # noqa: B008 - AgentDojo interface
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},  # noqa: B006 - AgentDojo interface
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        delay = 15.0
        for attempt in range(1, self.max_attempts + 1):
            wait = self.min_interval_s - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            try:
                return self.inner.query(query, runtime, env, messages, extra_args)
            except Exception as exc:  # noqa: BLE001 - provider errors vary
                status = getattr(exc, "status_code", None)
                transient = status in {429, 500, 502, 503, 504} or "timed out" in str(exc).lower()
                if not transient or attempt == self.max_attempts:
                    raise
                self._sleep(delay)
                delay = min(delay * 2, 120.0)
        raise RuntimeError("unreachable")


class ToolCallMetadataRelay:
    """Preserves provider-specific tool-call metadata across turns.

    Gemini's chat-completions compatible endpoint returns an opaque ``extra_content``
    (thought signature) on each tool call and rejects the next request unless it
    is sent back. AgentDojo's message format drops it, so this wrapper around
    ``client.chat.completions.create`` remembers it by tool-call id and re-attaches
    it to the assistant message. It changes transport only, not prompts or tools.
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self._create = client.chat.completions.create
        self._extra: dict[str, Any] = {}
        client.chat.completions.create = self.create

    def create(self, **kwargs: Any) -> Any:
        for message in kwargs.get("messages", []):
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            for call in message.get("tool_calls") or []:
                extra = self._extra.get(call.get("id"))
                if extra is not None and "extra_content" not in call:
                    call["extra_content"] = extra
        response = self._create(**kwargs)
        for choice in getattr(response, "choices", []) or []:
            for call in getattr(choice.message, "tool_calls", None) or []:
                extra = (getattr(call, "model_extra", None) or {}).get("extra_content")
                if extra is not None:
                    self._extra[call.id] = extra
        return response
