"""Security gateway: inspect → risk → (reconstruct) → policy → audit → forward.

This module is MCP-transport-agnostic so it can be unit-tested without I/O.
The MCP proxy server must never bypass this path for sensitive tools.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from agenttaint_audit.store import AuditStore
from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    ArgumentEvidence,
    DecisionOutcome,
    ProvenanceSpan,
    ProvenanceStatus,
    RiskTier,
    ToolCallDecision,
)
from agenttaint_policy.adapter import PolicyAdapter
from agenttaint_policy.context import PolicyContext
from agenttaint_policy.evidence import build_policy_context, reconstruct_authority_evidence
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


class ConfirmationBinder(Protocol):
    def request(self, **kwargs: Any) -> Any: ...

    def consume(self, **kwargs: Any) -> Any: ...


@dataclass
class EnforcementResult:
    decision: ToolCallDecision
    result: Any | None = None
    result_span: ProvenanceSpan | None = None
    confirmation: Any | None = None


@dataclass
class SecurityGateway:
    """Enforcement boundary between agents and tool backends."""

    backend: ToolBackend
    registry: ProvenanceRegistry
    risk: RiskClassifier
    policy: PolicyAdapter
    audit: AuditStore
    confirmation: ConfirmationBinder | None = None
    reconstruction: Any | None = None
    candidates: list[Any] = field(default_factory=list)
    user_authorized_values: set[str] = field(default_factory=set)
    authority_argument_names: set[str] = field(
        default_factory=lambda: {"to", "recipient", "url", "path", "command"}
    )
    registry_available: bool = True
    attach_reconstruction: bool = True

    def list_tools(self) -> list[ToolSpec]:
        return self.backend.list_tools()

    def _try_consume_confirmation(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str | None,
        confirmation_id: str | None,
        approval_token: str | None,
    ) -> tuple[bool, str | None, str | None]:
        """Return (validated, confirmation_id, error_explanation)."""
        if not confirmation_id:
            return False, None, None
        if self.confirmation is None:
            return False, confirmation_id, "confirmation service unavailable"
        try:
            self.confirmation.consume(
                confirmation_id=confirmation_id,
                tool=tool_name,
                arguments=arguments,
                agent_id=agent_id or "",
                approval_token=approval_token,
            )
            return True, confirmation_id, None
        except Exception as exc:  # noqa: BLE001 - map to fail-closed policy input
            return False, confirmation_id, f"confirmation rejected: {exc}"

    def _gather_evidence(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str | None,
        risk_tier: RiskTier,
        candidates: list[Any] | None,
    ) -> list[ArgumentEvidence]:
        if self.reconstruction is None:
            return []
        if risk_tier != RiskTier.HIGH:
            return []
        corpus = list(candidates if candidates is not None else self.candidates)
        if not corpus:
            return []
        return reconstruct_authority_evidence(
            engine=self.reconstruction,
            arguments=arguments,
            candidates=corpus,
            authority_argument_names=self.authority_argument_names,
            agent_id=agent_id,
            attach=self.attach_reconstruction,
        )

    def _evaluate(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str | None,
        confirmation_id: str | None,
        approval_token: str | None,
        argument_parent_span_ids: dict[str, list[str]] | None,
        candidates: list[Any] | None,
    ) -> tuple[Any, PolicyContext, ToolCallDecision]:
        risk_tier = self.risk.classify(tool_name, arguments)

        validated, cid, confirm_err = self._try_consume_confirmation(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
            confirmation_id=confirmation_id,
            approval_token=approval_token,
        )

        evidence = self._gather_evidence(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
            risk_tier=risk_tier,
            candidates=candidates,
        )

        ctx = build_policy_context(
            risk_tier=risk_tier,
            registry=self.registry if self.registry_available else None,
            registry_available=self.registry_available,
            argument_evidence=evidence,
            argument_parent_span_ids=argument_parent_span_ids,
            user_authorized_values=self.user_authorized_values,
            authority_argument_names=self.authority_argument_names,
            confirmation_id=cid,
            confirmation_validated=validated,
        )

        # Invalid confirmation attempt fails closed before policy soft-paths.
        if confirmation_id and not validated:
            from agenttaint_policy.adapter import PolicyResult

            policy_result = PolicyResult(
                decision=DecisionOutcome.BLOCK,
                policy_id="confirmation-invalid",
                explanation=confirm_err or "confirmation invalid",
            )
        else:
            policy_result = self.policy.evaluate(
                tool_name=tool_name,
                arguments=arguments,
                risk_tier=risk_tier,
                agent_id=agent_id,
                context=ctx,
            )

        decision = ToolCallDecision(
            agent_id=agent_id,
            tool=tool_name,
            risk_tier=risk_tier,
            arguments_hash=content_hash(_canonicalize_arguments(arguments)),
            arguments_redacted=_redact_arguments(arguments),
            evidence=evidence,
            provenance_status=ctx.provenance_status,
            decision=policy_result.decision,
            policy_id=policy_result.policy_id,
            confirmation_id=cid,
            explanation=policy_result.explanation,
            latency_ms=0,
        )
        return policy_result, ctx, decision

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        agent_id: str | None = None,
        raise_on_deny: bool = True,
        confirmation_id: str | None = None,
        approval_token: str | None = None,
        argument_parent_span_ids: dict[str, list[str]] | None = None,
        candidates: list[Any] | None = None,
    ) -> EnforcementResult:
        started = time.perf_counter()
        args = dict(arguments or {})
        policy_result, _ctx, decision = self._evaluate(
            tool_name=tool_name,
            arguments=args,
            agent_id=agent_id,
            confirmation_id=confirmation_id,
            approval_token=approval_token,
            argument_parent_span_ids=argument_parent_span_ids,
            candidates=candidates,
        )

        confirmation_record = None
        if policy_result.decision == DecisionOutcome.CONFIRM and self.confirmation is not None:
            confirmation_record = self.confirmation.request(
                tool=tool_name,
                arguments=args,
                agent_id=agent_id or "",
                risk_tier=decision.risk_tier,
                explanation=policy_result.explanation,
                arguments_redacted=_redact_arguments(args),
                policy_id=policy_result.policy_id,
            )
            decision.confirmation_id = confirmation_record.confirmation_id
            decision.explanation = (
                f"{policy_result.explanation} "
                f"confirmation_id={confirmation_record.confirmation_id}"
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
            return EnforcementResult(
                decision=decision, confirmation=confirmation_record
            )

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
        # Tool result labeling is KNOWN for the result itself; decision retains
        # pre-call argument provenance status for audit of the authorization.
        if decision.provenance_status == ProvenanceStatus.UNKNOWN and not decision.evidence:
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
        argument_parent_span_ids: dict[str, list[str]] | None = None,
        candidates: list[Any] | None = None,
    ) -> ToolCallDecision:
        """Evaluate policy without executing the tool or consuming confirmations."""
        args = dict(arguments or {})
        _policy_result, _ctx, decision = self._evaluate(
            tool_name=tool_name,
            arguments=args,
            agent_id=agent_id,
            confirmation_id=None,
            approval_token=None,
            argument_parent_span_ids=argument_parent_span_ids,
            candidates=candidates,
        )
        return decision
