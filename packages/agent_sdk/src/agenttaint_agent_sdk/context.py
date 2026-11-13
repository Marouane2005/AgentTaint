"""Instrumented agent context: transforms, memory, authenticated delegation."""

from __future__ import annotations

from typing import Any

from agenttaint_core.schemas import (
    EdgeRelationship,
    ProvenanceSpan,
    SpanKind,
    TransformationOperation,
)
from agenttaint_provenance.registry import ProvenanceRegistry

from agenttaint_agent_sdk.envelope import EnvelopeVerifier, ProvenanceEnvelope


class AgentTaintContext:
    """SDK surface for a single cooperating agent."""

    def __init__(
        self,
        *,
        agent_id: str,
        registry: ProvenanceRegistry,
        verifier: EnvelopeVerifier,
    ) -> None:
        self.agent_id = agent_id
        self.registry = registry
        self.verifier = verifier

    def summarize(
        self,
        text: str,
        parent_span_ids: list[str],
        *,
        model: str | None = None,
    ) -> ProvenanceSpan:
        span, _ = self.registry.record_transformation(
            operation=TransformationOperation.SUMMARIZATION,
            input_span_ids=parent_span_ids,
            output_content=text,
            agent_id=self.agent_id,
            model=model,
            kind=SpanKind.SUMMARY,
            relationship=EdgeRelationship.SUMMARIZED_FROM,
        )
        return span

    def rewrite(
        self,
        text: str,
        parent_span_ids: list[str],
        *,
        model: str | None = None,
    ) -> ProvenanceSpan:
        span, _ = self.registry.record_transformation(
            operation=TransformationOperation.REWRITE,
            input_span_ids=parent_span_ids,
            output_content=text,
            agent_id=self.agent_id,
            model=model,
            kind=SpanKind.REWRITE,
            relationship=EdgeRelationship.REWRITTEN_FROM,
        )
        return span

    def remember(self, span_id: str, key: str) -> ProvenanceSpan:
        span, _ = self.registry.store_in_memory(
            parent_span_id=span_id, key=key, agent_id=self.agent_id
        )
        return span

    def recall(self, memory_span_id: str) -> ProvenanceSpan:
        span, _ = self.registry.retrieve_from_memory(
            memory_span_id=memory_span_id, agent_id=self.agent_id
        )
        return span

    def mark_untracked(
        self, text: str, claimed_parent_ids: list[str] | None = None
    ) -> ProvenanceSpan:
        span, _ = self.registry.record_gap(
            reason="uninstrumented_llm_call",
            output_content=text,
            claimed_parent_ids=claimed_parent_ids,
            agent_id=self.agent_id,
        )
        return span

    def delegate(
        self,
        *,
        recipient_agent: str,
        content: str,
        parent_span_ids: list[str],
    ) -> ProvenanceEnvelope:
        return self.verifier.create(
            sender_agent=self.agent_id,
            recipient_agent=recipient_agent,
            content=content,
            parent_span_ids=parent_span_ids,
        )

    def accept(self, envelope: ProvenanceEnvelope | dict[str, Any]) -> ProvenanceSpan:
        return self.verifier.accept(envelope, expected_recipient=self.agent_id)
