"""Security gateway: inspect → risk → (reconstruct) → policy → audit → forward.

This module is MCP-transport-agnostic so it can be unit-tested without I/O.
The MCP proxy server must never bypass this path for sensitive tools.
"""

from __future__ import annotations

import inspect
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from agenttaint_agent_sdk.confirmation import ConfirmationQueueFull
from agenttaint_audit.store import AuditStore
from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    ArgumentEvidence,
    DecisionOutcome,
    Origin,
    ProvenanceSpan,
    RiskTier,
    ToolCallDecision,
)
from agenttaint_policy.adapter import PolicyAdapter
from agenttaint_policy.context import (
    DEFAULT_AUTHORITY_ARGUMENTS,
    DEFAULT_CONTENT_ARGUMENTS,
    PolicyContext,
)
from agenttaint_policy.evidence import build_policy_context, reconstruct_authority_evidence
from agenttaint_policy.grants import AuthorizationGrant
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_risk.classifier import RiskClassifier

from agenttaint_mcp_proxy.backends import ToolBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.registry_health import probe_registry_available

_UNTRUSTED_ORIGINS = frozenset({Origin.UNTRUSTED_TOOL, Origin.UNKNOWN})


def _canonicalize_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, default=str)


def _redact_value(value: Any) -> Any:
    """Recursively redact sensitive strings in nested argument structures."""
    if isinstance(value, str):
        return redact_sensitive(value)
    if isinstance(value, dict):
        return {str(k): _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, tuple):
        return [_redact_value(v) for v in value]
    return value


def _redact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _redact_value(v) for k, v in arguments.items()}


def provenance_context_hash(
    *,
    argument_parent_span_ids: dict[str, list[str]] | None,
    candidate_span_ids: list[str] | None = None,
) -> str:
    """Stable hash of provenance references bound into confirmations."""
    payload = {
        "parents": {
            str(k): sorted(str(x) for x in (v or []))
            for k, v in sorted((argument_parent_span_ids or {}).items())
        },
        "candidates": sorted(str(x) for x in (candidate_span_ids or [])),
    }
    return content_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))


_INVALID_SPAN_PREFIX = "invalid-span:"


def _accepts_kwarg(func: Any, name: str) -> bool:
    """True when ``func`` takes ``name`` (explicitly or via **kwargs)."""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())


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
    authorization_grants: list[AuthorizationGrant] = field(default_factory=list)
    # Deprecated: converted to wildcard grants when non-empty.
    user_authorized_values: set[str] = field(default_factory=set)
    authority_argument_names: set[str] = field(
        default_factory=lambda: set(DEFAULT_AUTHORITY_ARGUMENTS)
    )
    content_argument_names: set[str] = field(default_factory=lambda: set(DEFAULT_CONTENT_ARGUMENTS))
    # None → probe the registry on every evaluate; bool overrides for tests.
    registry_available: bool | None = None
    attach_reconstruction: bool = True
    # Evaluation-only: restrict reconstruction to some channels (benchmark ablations).
    reconstruction_ablation: Any | None = None
    session_id: str | None = None
    # Untrusted tool results this gateway has labeled (plaintext kept in-process only,
    # never persisted) so calls with undeclared lineage can still be reconstructed.
    session_untrusted: list[Any] = field(default_factory=list)
    max_session_candidates: int = 256
    # Serialises decisions so confirmation consumption, corpus updates and audit writes
    # cannot interleave when the proxy runs evaluations on worker threads.
    _lock: Any = field(default_factory=threading.RLock, repr=False, compare=False)
    # Hardened mode for callers that assert lineage over an untrusted wire (the MCP
    # proxy): declared parent spans are checked against the registry and the calling
    # agent, caller-supplied candidates only ever add to the corpus, declared lineage
    # never switches off session-wide reconstruction, and the reconstruction corpus is
    # isolated per agent/session. Off by default so in-process SDK callers and the
    # benchmark harness keep their existing semantics.
    strict_lineage: bool = False

    def list_tools(self) -> list[ToolSpec]:
        return self.backend.list_tools()

    def check_registry_available(self) -> bool:
        if self.registry_available is not None:
            return self.registry_available
        return probe_registry_available(self.registry)

    def label_tool_result(
        self,
        *,
        tool_name: str,
        content: str,
        agent_id: str | None,
        session_id: str | None = None,
    ) -> ProvenanceSpan:
        """Register a tool result span (serialised with decisions)."""
        with self._lock:
            return self._label_tool_result(
                tool_name=tool_name, content=content, agent_id=agent_id, session_id=session_id
            )

    def _label_tool_result(
        self,
        *,
        tool_name: str,
        content: str,
        agent_id: str | None,
        session_id: str | None = None,
    ) -> ProvenanceSpan:
        """Register a tool result span and remember untrusted text for reconstruction."""
        span = self.registry.record_tool_result(
            tool_name=tool_name,
            content=content,
            agent_id=agent_id,
        )
        if span.origin in _UNTRUSTED_ORIGINS and content:
            from agenttaint_reconstruction.engine import CandidateRecord

            self.session_untrusted.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=content,
                    origin=span.origin,
                    agent_id=agent_id,
                    session_id=session_id or self.session_id,
                )
            )
            overflow = len(self.session_untrusted) - self.max_session_candidates
            if overflow > 0:
                del self.session_untrusted[:overflow]
        return span

    def _registry_untrusted_spans(self) -> list[ProvenanceSpan]:
        try:
            return [s for s in self.registry.store.list_spans() if s.origin in _UNTRUSTED_ORIGINS]
        except Exception:  # noqa: BLE001 - availability handled by registry probe
            return []

    def _in_scope(
        self, agent_id: str | None, session_id: str | None, record_agent: Any, record_session: Any
    ) -> bool:
        """Per-agent / per-session isolation (only enforced in strict mode)."""
        if not self.strict_lineage:
            return True
        if agent_id is not None and record_agent not in (None, agent_id):
            return False
        effective = session_id or self.session_id
        return not (effective is not None and record_session not in (None, effective))

    def session_corpus(
        self, agent_id: str | None = None, session_id: str | None = None
    ) -> list[Any]:
        """Untrusted spans this session has seen, as reconstruction candidates."""
        from agenttaint_reconstruction.engine import CandidateRecord

        corpus: list[Any] = [
            c
            for c in self.session_untrusted
            if self._in_scope(
                agent_id, session_id, getattr(c, "agent_id", None), getattr(c, "session_id", None)
            )
        ]
        seen = {getattr(c, "span_id", None) for c in self.session_untrusted}
        for span in self._registry_untrusted_spans():
            if span.span_id in seen or not span.content_redacted:
                continue
            if not self._in_scope(agent_id, session_id, span.agent_id, None):
                continue
            corpus.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=span.content_redacted,
                    origin=span.origin,
                    agent_id=span.agent_id,
                )
            )
        return corpus

    def session_untrusted_seen(
        self, agent_id: str | None = None, session_id: str | None = None
    ) -> bool:
        if not self.strict_lineage:
            return bool(self.session_untrusted) or bool(self._registry_untrusted_spans())
        return bool(self.session_corpus(agent_id, session_id))

    def sanitize_declared_parents(
        self,
        parents: dict[str, list[str]] | None,
        *,
        agent_id: str | None,
    ) -> dict[str, list[str]] | None:
        """Neutralise declared parent spans that do not exist or belong to another agent.

        Invalid ids are rewritten to a sentinel that the registry cannot resolve, so
        policy sees UNKNOWN (untrusted) lineage instead of trusting the claim.
        """
        if not self.strict_lineage or not parents:
            return parents
        checked: dict[str, list[str]] = {}
        for arg, ids in parents.items():
            out: list[str] = []
            for sid in ids:
                try:
                    span = self.registry.store.get_span(sid)
                except Exception:  # noqa: BLE001 - treat store errors as unresolvable
                    span = None
                if span is None or span.agent_id not in (None, agent_id):
                    out.append(f"{_INVALID_SPAN_PREFIX}{sid}")
                else:
                    out.append(sid)
            checked[arg] = out
        return checked

    def release_confirmation(self, confirmation_id: str | None) -> bool:
        """Give back an approval whose action provably never reached the backend."""
        release = getattr(self.confirmation, "release", None)
        if not confirmation_id or not callable(release):
            return False
        try:
            return bool(release(confirmation_id))
        except Exception:  # noqa: BLE001 - best effort; stays consumed (fail closed)
            return False

    def _try_consume_confirmation(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str | None,
        confirmation_id: str | None,
        approval_token: str | None,
        provenance_context_hash_value: str | None,
    ) -> tuple[bool, str | None, str | None]:
        """Return (validated, confirmation_id, error_explanation)."""
        if not confirmation_id:
            return False, None, None
        if self.confirmation is None:
            return False, confirmation_id, "confirmation service unavailable"
        if not approval_token:
            # The approval token is issued to the human approver out-of-band and must be
            # presented by the caller. It is never read back from the confirmation
            # record: knowing only a confirmation_id must never be enough to execute.
            return (
                False,
                confirmation_id,
                "confirmation rejected: approval_token required (the approver receives it "
                "when approving; pass it as _agenttaint.approval_token)",
            )
        kwargs: dict[str, Any] = {
            "confirmation_id": confirmation_id,
            "tool": tool_name,
            "arguments": arguments,
            "agent_id": agent_id or "",
            "approval_token": approval_token,
        }
        if _accepts_kwarg(self.confirmation.consume, "provenance_context_hash"):
            kwargs["provenance_context_hash"] = provenance_context_hash_value
        try:
            self.confirmation.consume(**kwargs)
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
        lineage_declared: bool = True,
        session_id: str | None = None,
        read_only: bool = False,
    ) -> list[ArgumentEvidence]:
        _ = tool_name
        if self.reconstruction is None:
            return []
        if risk_tier == RiskTier.LOW:
            return []
        # Independent verification always runs for MEDIUM and HIGH calls. Declared lineage
        # is additional evidence, never a replacement for it: caller-supplied candidates
        # are additive, and the session-wide corpus is included whether or not the caller
        # declared parents (omitting or forging lineage must never hide untrusted text).
        _ = lineage_declared
        corpus = list(self.candidates)
        have = {getattr(c, "span_id", None) for c in corpus}
        corpus.extend(c for c in (candidates or []) if getattr(c, "span_id", None) not in have)
        have = {getattr(c, "span_id", None) for c in corpus}
        corpus.extend(c for c in self.session_corpus(agent_id, session_id) if c.span_id not in have)
        if not corpus:
            return []
        return reconstruct_authority_evidence(
            engine=self.reconstruction,
            arguments=arguments,
            candidates=corpus,
            authority_argument_names=self.authority_argument_names,
            content_argument_names=self.content_argument_names,
            agent_id=agent_id,
            attach=self.attach_reconstruction and not read_only,
            ablation=self.reconstruction_ablation,
        )

    def invoke(self, *args: Any, **kwargs: Any) -> EnforcementResult:
        """Evaluate (and, unless ``execute=False``, forward) one tool call."""
        with self._lock:
            return self._invoke(*args, **kwargs)

    def preview(self, *args: Any, **kwargs: Any) -> ToolCallDecision:
        """Evaluate policy without side effects."""
        with self._lock:
            return self._preview(*args, **kwargs)

    def audit_pending(self, decision: ToolCallDecision) -> None:
        """Write-ahead record for an ALLOW that is about to be forwarded."""
        if callable(getattr(self.audit, "update", None)):
            self.audit.record(decision)

    def audit_final(self, decision: ToolCallDecision) -> None:
        """Record the outcome (upsert when a pending row exists)."""
        update = getattr(self.audit, "update", None)
        if callable(update):
            update(decision)
        else:
            self.audit.record(decision)

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
        session_id: str | None = None,
        provenance_context_hash_value: str | None = None,
        read_only: bool = False,
    ) -> tuple[Any, PolicyContext, ToolCallDecision, str]:
        argument_parent_span_ids = self.sanitize_declared_parents(
            argument_parent_span_ids, agent_id=agent_id
        )
        risk_tier = self.risk.classify(tool_name, arguments)
        registry_ok = self.check_registry_available()

        cand_ids: list[str] = []
        for c in candidates or []:
            sid = getattr(c, "span_id", None)
            if sid is None and isinstance(c, dict):
                sid = c.get("span_id")
            if sid:
                cand_ids.append(str(sid))
        # Always computed server-side: a caller-supplied hash could otherwise replay
        # an approval against different provenance references.
        _ = provenance_context_hash_value
        ctx_hash = provenance_context_hash(
            argument_parent_span_ids=argument_parent_span_ids,
            candidate_span_ids=cand_ids,
        )
        lineage_declared = any(bool(v) for v in (argument_parent_span_ids or {}).values())

        validated, cid, confirm_err = self._try_consume_confirmation(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
            confirmation_id=confirmation_id,
            approval_token=approval_token,
            provenance_context_hash_value=ctx_hash,
        )

        evidence = self._gather_evidence(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
            risk_tier=risk_tier,
            candidates=candidates,
            lineage_declared=lineage_declared,
            session_id=session_id,
            read_only=read_only,
        )

        ctx = build_policy_context(
            risk_tier=risk_tier,
            registry=self.registry if registry_ok else None,
            registry_available=registry_ok,
            argument_evidence=evidence,
            argument_parent_span_ids=argument_parent_span_ids,
            authorization_grants=self.authorization_grants,
            user_authorized_values=self.user_authorized_values,
            authority_argument_names=self.authority_argument_names,
            content_argument_names=self.content_argument_names,
            confirmation_id=cid,
            confirmation_validated=validated,
            agent_id=agent_id,
            session_id=session_id or self.session_id,
            tool_name=tool_name,
            session_untrusted_seen=(not lineage_declared)
            and self.session_untrusted_seen(agent_id, session_id),
        )

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
        return policy_result, ctx, decision, ctx_hash

    def _invoke(
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
        session_id: str | None = None,
        provenance_context_hash_value: str | None = None,
        execute: bool = True,
    ) -> EnforcementResult:
        started = time.perf_counter()
        args = dict(arguments or {})
        policy_result, _ctx, decision, ctx_hash = self._evaluate(
            tool_name=tool_name,
            arguments=args,
            agent_id=agent_id,
            confirmation_id=confirmation_id,
            approval_token=approval_token,
            argument_parent_span_ids=argument_parent_span_ids,
            candidates=candidates,
            session_id=session_id,
            provenance_context_hash_value=provenance_context_hash_value,
        )

        confirmation_record = None
        if policy_result.decision == DecisionOutcome.CONFIRM and self.confirmation is not None:
            request_kwargs: dict[str, Any] = {
                "tool": tool_name,
                "arguments": args,
                "agent_id": agent_id or "",
                "risk_tier": decision.risk_tier,
                "explanation": policy_result.explanation,
                "arguments_redacted": _redact_arguments(args),
                "policy_id": policy_result.policy_id,
            }
            if _accepts_kwarg(self.confirmation.request, "provenance_context_hash"):
                request_kwargs["provenance_context_hash"] = ctx_hash
            try:
                confirmation_record = self.confirmation.request(**request_kwargs)
            except ConfirmationQueueFull as exc:
                from agenttaint_policy.adapter import PolicyResult

                policy_result = PolicyResult(
                    decision=DecisionOutcome.BLOCK,
                    policy_id="confirmation-queue-full",
                    explanation=f"Blocked: too many unresolved confirmations ({exc}).",
                )
                decision.decision = policy_result.decision
                decision.policy_id = policy_result.policy_id
                decision.explanation = policy_result.explanation
            else:
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
            return EnforcementResult(decision=decision, confirmation=confirmation_record)

        # Write-ahead: the ALLOW is on record before anything is forwarded.
        self.audit_pending(decision)
        if not execute:
            decision.latency_ms = int((time.perf_counter() - started) * 1000)
            return EnforcementResult(decision=decision, confirmation=confirmation_record)

        try:
            raw_result = self.backend.call_tool(tool_name, args)
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            decision.decision = DecisionOutcome.BLOCK
            decision.policy_id = "backend-error"
            decision.explanation = f"Backend failure after ALLOW: {exc}"
            decision.latency_ms = int((time.perf_counter() - started) * 1000)
            self.audit_final(decision)
            raise

        result_text = (
            raw_result
            if isinstance(raw_result, str)
            else json.dumps(raw_result, sort_keys=True, default=str)
        )
        span = self.label_tool_result(
            tool_name=tool_name,
            content=result_text,
            agent_id=agent_id,
            session_id=session_id,
        )
        decision.latency_ms = int((time.perf_counter() - started) * 1000)
        decision.explanation = (
            f"{policy_result.explanation} Provenance span={span.span_id} "
            f"origin={span.origin.value}."
        )
        self.audit_final(decision)
        return EnforcementResult(decision=decision, result=raw_result, result_span=span)

    def _preview(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        agent_id: str | None = None,
        argument_parent_span_ids: dict[str, list[str]] | None = None,
        candidates: list[Any] | None = None,
        session_id: str | None = None,
    ) -> ToolCallDecision:
        """Evaluate policy without executing the tool or consuming confirmations."""
        args = dict(arguments or {})
        _policy_result, _ctx, decision, _ctx_hash = self._evaluate(
            tool_name=tool_name,
            arguments=args,
            agent_id=agent_id,
            confirmation_id=None,
            approval_token=None,
            argument_parent_span_ids=argument_parent_span_ids,
            candidates=candidates,
            session_id=session_id,
            read_only=True,
        )
        return decision
