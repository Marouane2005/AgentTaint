"""Security gateway: inspect → risk → policy → audit → (maybe) forward → label.

This module is MCP-transport-agnostic so it can be unit-tested without I/O.
The MCP proxy server must never bypass this path for sensitive tools.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from agenttaint_audit.store import AuditStore
from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    DecisionOutcome,
    ProvenanceSpan,
    ProvenanceStatus,
    ToolCallDecision,
)
from agenttaint_policy.adapter import PolicyAdapter
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_risk.classifier import RiskClassifier

from agenttaint_mcp_proxy.backends import ToolBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError


def _canonicalize_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, default=str)


def _redact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            redacted[key] = redact_sensitive(value)
        else:
            redacted[key] = value
    return redacted


@dataclass
class EnforcementResult:
    decision: ToolCallDecision
    result: Any | None = None
    result_span: ProvenanceSpan | None = None


class SecurityGateway:
    """Enforcement boundary between agents and tool backends."""

    def __init__(
        self,
        *,
        backend: ToolBackend,
        registry: ProvenanceRegistry,
        risk: RiskClassifier,
        policy: PolicyAdapter,
        audit: AuditStore,
    ) -> None:
        self.backend = backend
        self.registry = registry
        self.risk = risk
        self.policy = policy
        self.audit = audit

    def list_tools(self) -> list[ToolSpec]:
        return self.backend.list_tools()

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        agent_id: str | None = None,
        raise_on_deny: bool = True,
    ) -> EnforcementResult:
        started = time.perf_counter()
        args = dict(arguments or {})
        risk_tier = self.risk.classify(tool_name, args)
        policy_result = self.policy.evaluate(
            tool_name=tool_name,
            arguments=args,
            risk_tier=risk_tier,
            agent_id=agent_id,
        )

        decision = ToolCallDecision(
            agent_id=agent_id,
            tool=tool_name,
            risk_tier=risk_tier,
            arguments_hash=content_hash(_canonicalize_arguments(args)),
            arguments_redacted=_redact_arguments(args),
            provenance_status=ProvenanceStatus.UNKNOWN,
            decision=policy_result.decision,
            policy_id=policy_result.policy_id,
            explanation=policy_result.explanation,
            latency_ms=0,
        )

        if policy_result.decision != DecisionOutcome.ALLOW:
            decision.latency_ms = int((time.perf_counter() - started) * 1000)
            self.audit.record(decision)
            if raise_on_deny:
                raise EnforcementError(
                    f"AgentTaint {policy_result.decision.value}: {policy_result.explanation} "
                    f"(call_id={decision.call_id}, policy={policy_result.policy_id})",
                    decision=decision,
                )
            return EnforcementResult(decision=decision)

        # Never skip labeling or audit after a successful policy allow.
        try:
            raw_result = self.backend.call_tool(tool_name, args)
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            decision.decision = DecisionOutcome.BLOCK
            decision.policy_id = "backend-error"
            decision.explanation = f"Backend failure after ALLOW: {exc}"
            decision.latency_ms = int((time.perf_counter() - started) * 1000)
            self.audit.record(decision)
            raise

        result_text = (
            raw_result
            if isinstance(raw_result, str)
            else json.dumps(raw_result, sort_keys=True, default=str)
        )
        span = self.registry.record_tool_result(
            tool_name=tool_name,
            content=result_text,
            agent_id=agent_id,
        )
        decision.provenance_status = span.provenance_status
        decision.latency_ms = int((time.perf_counter() - started) * 1000)
        decision.explanation = (
            f"{policy_result.explanation} Provenance span={span.span_id} "
            f"origin={span.origin.value}."
        )
        self.audit.record(decision)
        return EnforcementResult(decision=decision, result=raw_result, result_span=span)

    def preview(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        agent_id: str | None = None,
    ) -> ToolCallDecision:
        """Evaluate policy without executing the tool."""
        args = dict(arguments or {})
        risk_tier = self.risk.classify(tool_name, args)
        policy_result = self.policy.evaluate(
            tool_name=tool_name,
            arguments=args,
            risk_tier=risk_tier,
            agent_id=agent_id,
        )
        return ToolCallDecision(
            agent_id=agent_id,
            tool=tool_name,
            risk_tier=risk_tier,
            arguments_hash=content_hash(_canonicalize_arguments(args)),
            arguments_redacted=_redact_arguments(args),
            provenance_status=ProvenanceStatus.UNKNOWN,
            decision=policy_result.decision,
            policy_id=policy_result.policy_id,
            explanation=policy_result.explanation,
        )
