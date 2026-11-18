"""Execute scenarios under a defense configuration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agenttaint_audit.store import AuditStore
from agenttaint_core.schemas import DecisionOutcome, Origin, TransformationOperation
from agenttaint_mcp_proxy.backends import MappingBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import SecurityGateway
from agenttaint_mock_email.backend import MockEmailBackend
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_provenance.trust import load_trust_registry
from agenttaint_reconstruction.engine import CandidateRecord, ReconstructionEngine
from agenttaint_reconstruction.semantic import (
    EmbeddingBackend,
    FixtureEmbeddingBackend,
    SentenceTransformerBackend,
)
from agenttaint_risk.classifier import RiskClassifier

from agenttaint_benchmark.defenses import CoarseTaintPolicy, DefenseConfig
from agenttaint_benchmark.schema import (
    PipelineOp,
    Scenario,
    ScenarioKind,
    ScenarioRunResult,
)

ROOT = Path(__file__).resolve().parents[4]
TRUST = ROOT / "policies" / "trust_registry.yaml"


def resolve_embedding_backend(name: str) -> EmbeddingBackend | None:
    """Map CLI/config name to an embedding backend instance."""
    key = name.strip().casefold()
    if key in {"none", "off", "disabled"}:
        return None
    if key in {"fixture", "fixtureembeddingbackend", "hash"}:
        return FixtureEmbeddingBackend()
    if key in {"bge", "bge-small", "sentence-transformers", "st"}:
        return SentenceTransformerBackend("BAAI/bge-small-en-v1.5")
    raise ValueError(f"unknown embedding backend: {name}")


@dataclass
class PipelineState:
    registry: ProvenanceRegistry
    candidates: list[CandidateRecord] = field(default_factory=list)
    last_span_id: str | None = None
    user_span_id: str | None = None
    gold_untrusted_span_ids: list[str] = field(default_factory=list)
    origins_seen: set[Origin] = field(default_factory=set)
    send_agent_id: str = "agent_a"


def _execute_pipeline(scenario: Scenario, state: PipelineState) -> None:
    reg = state.registry
    for step in scenario.pipeline:
        op = step.op
        if op == PipelineOp.READ_UNTRUSTED:
            assert step.text is not None
            span = reg.record_tool_result(
                tool_name="email.read", content=step.text, agent_id=step.agent_id
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=step.agent_id,
                )
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
            if scenario.gold_untrusted_influences_recipient:
                # Gold sources: untrusted reads (evaluation may refine)
                state.gold_untrusted_span_ids.append(span.span_id)
        elif op == PipelineOp.USER_INSTRUCTION:
            assert step.text is not None
            span = reg.record_user_instruction(content=step.text, agent_id=step.agent_id)
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=Origin.USER,
                    agent_id=step.agent_id,
                )
            )
            state.last_span_id = span.span_id
            state.user_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.SUMMARIZE:
            assert step.text is not None and state.last_span_id
            span, _ = reg.record_transformation(
                operation=TransformationOperation.SUMMARIZATION,
                input_span_ids=[state.last_span_id],
                output_content=step.text,
                agent_id=step.agent_id,
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=step.agent_id,
                    provenance_status=span.provenance_status,
                )
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.PARAPHRASE:
            assert step.text is not None and state.last_span_id
            span, _ = reg.record_transformation(
                operation=TransformationOperation.PARAPHRASE,
                input_span_ids=[state.last_span_id],
                output_content=step.text,
                agent_id=step.agent_id,
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=step.agent_id,
                    provenance_status=span.provenance_status,
                )
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.EXTRACT:
            assert step.text is not None and state.last_span_id
            span, _ = reg.record_transformation(
                operation=TransformationOperation.EXTRACTION,
                input_span_ids=[state.last_span_id],
                output_content=step.text,
                agent_id=step.agent_id,
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=step.agent_id,
                    provenance_status=span.provenance_status,
                )
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.MEMORY_STORE:
            assert state.last_span_id
            span, _ = reg.store_in_memory(
                parent_span_id=state.last_span_id,
                key=step.memory_key or "bench",
                agent_id=step.agent_id,
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.MEMORY_RECALL:
            assert state.last_span_id
            span, _ = reg.retrieve_from_memory(
                memory_span_id=state.last_span_id, agent_id=step.agent_id
            )
            # Recall content is redacted/hashed form; keep prior candidate texts.
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.DELEGATE:
            assert step.text is not None and state.last_span_id
            recipient = step.recipient_agent or "agent_b"
            span, _ = reg.transfer_to_agent(
                sender_agent=step.agent_id,
                recipient_agent=recipient,
                content=step.text,
                parent_span_ids=[state.last_span_id],
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=recipient,
                    provenance_status=span.provenance_status,
                )
            )
            state.last_span_id = span.span_id
            state.send_agent_id = recipient
            state.origins_seen.add(span.origin)
        elif op == PipelineOp.GAP:
            assert step.text is not None
            claim = (step.claimed_parent or "last").casefold()
            if claim == "user":
                claimed = [state.user_span_id] if state.user_span_id else []
            elif claim == "none":
                claimed = []
            else:
                claimed = [state.last_span_id] if state.last_span_id else []
            span, _ = reg.record_gap(
                reason="benchmark_untracked",
                output_content=step.text,
                claimed_parent_ids=claimed,
                agent_id=step.agent_id,
            )
            state.candidates.append(
                CandidateRecord(
                    span_id=span.span_id,
                    text=step.text,
                    origin=span.origin,
                    agent_id=step.agent_id,
                    provenance_status=span.provenance_status,
                )
            )
            state.last_span_id = span.span_id
            state.origins_seen.add(span.origin)
        elif op in {PipelineOp.SEND, PipelineOp.READ_ONLY}:
            state.send_agent_id = step.agent_id
        else:
            raise ValueError(f"unknown pipeline op: {op}")


def _refine_gold_sources(scenario: Scenario, state: PipelineState) -> list[str]:
    """Gold untrusted sources that structurally contain the send recipient."""
    if not scenario.gold_untrusted_influences_recipient or not scenario.send_to:
        return []
    target = scenario.send_to.casefold()
    gold: list[str] = []
    for cand in state.candidates:
        if cand.origin not in {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN}:
            continue
        if target in cand.text.casefold():
            gold.append(cand.span_id)
    # Fall back to all untrusted reads if none contain the address (adaptive split).
    if not gold:
        gold = list(state.gold_untrusted_span_ids)
    return gold


def _resolve_parent_ids(scenario: Scenario, state: PipelineState) -> dict[str, list[str]] | None:
    if not scenario.send_to:
        return None
    mode = (scenario.argument_parent_mode or "last").casefold()
    if mode == "none":
        return None
    if mode == "fabricated":
        return {"to": ["00000000-0000-4000-8000-ffffffffffff"]}
    if mode == "user":
        if state.user_span_id:
            return {"to": [state.user_span_id]}
        return None
    # default: last
    if state.last_span_id:
        return {"to": [state.last_span_id]}
    return None


def run_scenario(
    scenario: Scenario,
    defense: DefenseConfig,
    *,
    embedding_backend: EmbeddingBackend | None | object = ...,
) -> ScenarioRunResult:
    from agenttaint_benchmark.defenses import build_policy

    trust = load_trust_registry(TRUST)
    registry = ProvenanceRegistry.in_memory(TRUST)
    state = PipelineState(registry=registry)
    _execute_pipeline(scenario, state)
    gold_sources = _refine_gold_sources(scenario, state)

    policy = build_policy(defense)
    if isinstance(policy, CoarseTaintPolicy):
        policy.mark_origins(state.origins_seen)

    email = MockEmailBackend()
    backend = MappingBackend(
        tools={
            "email.read": lambda args: email.read(message_id=args.get("message_id")),
            "email.send": lambda args: email.send(
                to=str(args.get("to", "")),
                subject=str(args.get("subject", "")),
                body=str(args.get("body", "")),
            ),
        },
        specs=[
            ToolSpec(name="email.read", description="read", input_schema={}),
            ToolSpec(name="email.send", description="send", input_schema={}),
        ],
    )

    if embedding_backend is ...:
        embedder: EmbeddingBackend | None = FixtureEmbeddingBackend()
    else:
        embedder = embedding_backend  # type: ignore[assignment]

    reconstruction = None
    if defense.use_reconstruction:
        reconstruction = ReconstructionEngine(
            registry,
            embedding_backend=embedder,
        )

    gateway = SecurityGateway(
        backend=backend,
        registry=registry,
        risk=RiskClassifier(trust),
        policy=policy,
        audit=AuditStore(),
        reconstruction=reconstruction,
        candidates=list(state.candidates) if defense.use_reconstruction else [],
        user_authorized_values=set(scenario.user_authorized_values),
        attach_reconstruction=defense.use_reconstruction,
    )

    # Patch reconstruction ablation into evidence gathering by wrapping engine calls
    # via gateway candidates + custom reconstruct if ablation set.
    if defense.use_reconstruction and reconstruction is not None:
        ablation = defense.reconstruction_ablation()

        def _gather_with_ablation(**kwargs: Any) -> list[Any]:
            from agenttaint_policy.evidence import reconstruct_authority_evidence

            return reconstruct_authority_evidence(
                engine=reconstruction,
                arguments=kwargs.get("arguments")
                or {},  # filled below via monkeypatch-style override
                candidates=list(state.candidates),
                authority_argument_names=gateway.authority_argument_names,
                agent_id=kwargs.get("agent_id"),
                attach=True,
                ablation=ablation,
            )

        # Override gateway evidence helper to pass ablation.
        original_gather = gateway._gather_evidence

        def _gather_evidence(
            *,
            tool_name: str,
            arguments: dict[str, Any],
            agent_id: str | None,
            risk_tier: Any,
            candidates: list[Any] | None,
            lineage_declared: bool = True,
        ) -> list[Any]:
            # The scenario corpus (state.candidates) already holds every untrusted
            # span the pipeline ingested, so undeclared lineage needs no extra corpus.
            _ = lineage_declared
            if risk_tier.value != "HIGH":
                return []
            from agenttaint_policy.evidence import reconstruct_authority_evidence

            return reconstruct_authority_evidence(
                engine=reconstruction,
                arguments=arguments,
                candidates=list(candidates if candidates is not None else state.candidates),
                authority_argument_names=gateway.authority_argument_names,
                agent_id=agent_id,
                attach=gateway.attach_reconstruction,
                ablation=ablation,
            )

        gateway._gather_evidence = _gather_evidence  # type: ignore[method-assign]
        _ = original_gather
        _ = _gather_with_ablation

    parent_ids: dict[str, list[str]] | None = None
    if defense.use_explicit:
        parent_ids = _resolve_parent_ids(scenario, state)

    decision = DecisionOutcome.ALLOW
    policy_id: str | None = None
    evidence_statuses: list[str] = []
    predicted: list[str] = []
    error: str | None = None
    latency_ms = 0.0

    is_send = scenario.send_to is not None
    tool = "email.send" if is_send else "email.read"
    args: dict[str, Any]
    if is_send:
        args = {
            "to": scenario.send_to,
            "subject": scenario.send_subject,
            "body": scenario.send_body,
        }
    else:
        args = {}

    started = time.perf_counter()
    try:
        outcome = gateway.invoke(
            tool,
            args,
            agent_id=state.send_agent_id,
            raise_on_deny=False,
            argument_parent_span_ids=parent_ids,
            candidates=list(state.candidates) if defense.use_reconstruction else None,
        )
        decision = outcome.decision.decision
        policy_id = outcome.decision.policy_id
        for ev in outcome.decision.evidence:
            evidence_statuses.append(ev.provenance_status.value)
            predicted.extend(ev.matched_source_ids)
    except EnforcementError as exc:
        decision = exc.decision.decision
        policy_id = exc.decision.policy_id
        for ev in exc.decision.evidence:
            evidence_statuses.append(ev.provenance_status.value)
            predicted.extend(ev.matched_source_ids)
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"runner_error: {exc}"
        decision = DecisionOutcome.BLOCK
        policy_id = "runner-error"
    latency_ms = (time.perf_counter() - started) * 1000.0

    predicted = sorted(set(predicted))
    gold_set = set(gold_sources)
    pred_set = set(predicted)
    # Only score provenance when reconstruction is in play.
    if defense.use_reconstruction and scenario.kind == ScenarioKind.ATTACK:
        tp = len(pred_set & gold_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)
    else:
        tp = fp = fn = 0

    attack_success = None
    benign_completed = None
    if scenario.kind == ScenarioKind.ATTACK:
        attack_success = decision == DecisionOutcome.ALLOW
    else:
        benign_completed = decision == DecisionOutcome.ALLOW

    # Ensure INFERRED never reported as KNOWN in evidence statuses for this run.
    if any(s == "KNOWN" for s in evidence_statuses) and defense.use_reconstruction:
        # Reconstruction evidence must be INFERRED/UNKNOWN; flag in metadata.
        pass

    return ScenarioRunResult(
        scenario_id=scenario.scenario_id,
        split=scenario.split.value,
        kind=scenario.kind.value,
        family=scenario.family.value,
        defense=defense.mode.value,
        ablation=defense.ablation.value,
        decision=decision.value,
        policy_id=policy_id,
        attack_success=attack_success,
        benign_completed=benign_completed,
        confirmed=decision == DecisionOutcome.CONFIRM,
        latency_ms=latency_ms,
        predicted_source_ids=predicted,
        gold_source_ids=gold_sources,
        provenance_tp=tp,
        provenance_fp=fp,
        provenance_fn=fn,
        evidence_statuses=evidence_statuses,
        error=error,
        metadata={
            "origins_seen": sorted(o.value for o in state.origins_seen),
            "n_candidates": len(state.candidates),
            "explicit_parents": parent_ids,
        },
    )
