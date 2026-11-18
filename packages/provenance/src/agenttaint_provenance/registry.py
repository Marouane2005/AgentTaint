"""High-level provenance registry used by the proxy and SDK."""

from __future__ import annotations

from pathlib import Path

from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    EdgeRelationship,
    EvidenceType,
    LineageCompleteness,
    Origin,
    OriginConflict,
    ProvenanceEdge,
    ProvenanceSpan,
    ProvenanceStatus,
    SpanKind,
    TransformationOperation,
    TransformationRecord,
)

from agenttaint_provenance.graph import ProvenanceGraph
from agenttaint_provenance.labeler import SourceLabeler
from agenttaint_provenance.lineage import analyze_completeness, detect_origin_conflicts
from agenttaint_provenance.store import ProvenanceStore
from agenttaint_provenance.trust import TrustRegistry, load_trust_registry

_ORIGIN_RANK = {
    Origin.USER: 0,
    Origin.TRUSTED_TOOL: 1,
    Origin.INTERNAL: 2,
    Origin.UNTRUSTED_TOOL: 3,
    Origin.UNKNOWN: 4,
}

_OP_TO_RELATIONSHIP = {
    TransformationOperation.SUMMARIZATION: EdgeRelationship.SUMMARIZED_FROM,
    TransformationOperation.REWRITE: EdgeRelationship.REWRITTEN_FROM,
    TransformationOperation.PARAPHRASE: EdgeRelationship.REWRITTEN_FROM,
    TransformationOperation.EXTRACTION: EdgeRelationship.EXTRACTED_FROM,
    TransformationOperation.MEMORY_STORE: EdgeRelationship.STORED_IN_MEMORY,
    TransformationOperation.MEMORY_RETRIEVE: EdgeRelationship.RETRIEVED_FROM_MEMORY,
    TransformationOperation.AGENT_DELEGATION: EdgeRelationship.TRANSFERRED_TO_AGENT,
    TransformationOperation.TOOL_RESULT: EdgeRelationship.DERIVED_FROM,
    TransformationOperation.UNTRACKED: EdgeRelationship.GAP_FROM,
}

_OP_TO_KIND = {
    TransformationOperation.SUMMARIZATION: SpanKind.SUMMARY,
    TransformationOperation.REWRITE: SpanKind.REWRITE,
    TransformationOperation.PARAPHRASE: SpanKind.REWRITE,
    TransformationOperation.EXTRACTION: SpanKind.EXTRACT,
    TransformationOperation.MEMORY_STORE: SpanKind.MEMORY,
    TransformationOperation.MEMORY_RETRIEVE: SpanKind.MEMORY,
    TransformationOperation.AGENT_DELEGATION: SpanKind.AGENT_MESSAGE,
    TransformationOperation.TOOL_RESULT: SpanKind.TOOL_RESULT,
    TransformationOperation.UNTRACKED: SpanKind.GAP,
}


class ProvenanceRegistry:
    """Single entry point for creating and querying provenance."""

    def __init__(
        self,
        store: ProvenanceStore,
        trust: TrustRegistry,
        *,
        retain_redacted: bool = True,
    ) -> None:
        self.store = store
        self.trust = trust
        self.labeler = SourceLabeler(trust, retain_redacted=retain_redacted)
        self.graph = ProvenanceGraph(store)
        self.graph.rebuild()

    @classmethod
    def in_memory(cls, trust_registry_path: str | Path) -> ProvenanceRegistry:
        return cls(
            store=ProvenanceStore("sqlite+pysqlite:///:memory:"),
            trust=load_trust_registry(trust_registry_path),
        )

    def register_span(self, span: ProvenanceSpan) -> ProvenanceSpan:
        self.store.put_span(span)
        self.graph.add_span(span)
        return span

    def link(
        self,
        *,
        src_span_id: str,
        dst_span_id: str,
        relationship: EdgeRelationship,
        evidence_type: EvidenceType = EvidenceType.EXPLICIT,
        metadata: dict[str, object] | None = None,
    ) -> ProvenanceEdge:
        if self.store.get_span(src_span_id) is None:
            raise ValueError(f"missing src span: {src_span_id}")
        if self.store.get_span(dst_span_id) is None:
            raise ValueError(f"missing dst span: {dst_span_id}")
        if evidence_type == EvidenceType.INFERRED:
            dst = self.store.get_span(dst_span_id)
            assert dst is not None
            if dst.provenance_status == ProvenanceStatus.KNOWN:
                raise ValueError(
                    "refusing to attach INFERRED edge to a KNOWN span; "
                    "create an INFERRED span or use EXPLICIT instrumentation"
                )
        edge = ProvenanceEdge(
            src_span_id=src_span_id,
            dst_span_id=dst_span_id,
            relationship=relationship,
            evidence_type=evidence_type,
            metadata=dict(metadata or {}),
        )
        self.store.put_edge(edge)
        self.graph.add_edge(edge)
        return edge

    def record_tool_result(
        self,
        *,
        tool_name: str,
        content: str,
        agent_id: str | None = None,
        path: str | None = None,
    ) -> ProvenanceSpan:
        span = self.labeler.label_tool_result(
            tool_name=tool_name,
            content=content,
            agent_id=agent_id,
            path=path,
        )
        return self.register_span(span)

    def record_user_instruction(
        self, *, content: str, agent_id: str | None = None
    ) -> ProvenanceSpan:
        span = self.labeler.label_user_instruction(content=content, agent_id=agent_id)
        return self.register_span(span)

    def _least_trust_origin(self, input_span_ids: list[str]) -> Origin:
        least_trust = Origin.USER
        for input_id in input_span_ids:
            parent = self.store.get_span(input_id)
            if parent is None:
                return Origin.UNKNOWN
            if _ORIGIN_RANK[parent.origin] > _ORIGIN_RANK[least_trust]:
                least_trust = parent.origin
        return least_trust

    def _parents_incomplete(self, input_span_ids: list[str]) -> bool:
        for input_id in input_span_ids:
            parent = self.store.get_span(input_id)
            if parent is None:
                return True
            if parent.kind == SpanKind.GAP:
                return True
            if parent.provenance_status in {
                ProvenanceStatus.PARTIAL,
                ProvenanceStatus.UNKNOWN,
                ProvenanceStatus.INFERRED,
            }:
                return True
        return False

    def record_transformation(
        self,
        *,
        operation: TransformationOperation,
        input_span_ids: list[str],
        output_content: str,
        agent_id: str | None = None,
        model: str | None = None,
        kind: SpanKind | None = None,
        relationship: EdgeRelationship | None = None,
        instrumentation: str = "SDK",
        metadata: dict[str, object] | None = None,
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        """Record an instrumented transformation with explicit parent links.

        Non-SDK instrumentation yields PARTIAL and never claims complete KNOWN lineage.
        """
        if not input_span_ids:
            raise ValueError("transformations require at least one input span")
        missing = [i for i in input_span_ids if self.store.get_span(i) is None]
        if missing:
            raise ValueError(f"unknown input span(s): {missing}")
        if operation == TransformationOperation.UNTRACKED:
            raise ValueError("use record_gap() for untracked transformations")

        status = ProvenanceStatus.KNOWN if instrumentation == "SDK" else ProvenanceStatus.PARTIAL
        if self._parents_incomplete(input_span_ids) and status == ProvenanceStatus.KNOWN:
            status = ProvenanceStatus.PARTIAL

        least_trust = self._least_trust_origin(input_span_ids)
        out_kind = kind or _OP_TO_KIND.get(operation, SpanKind.SUMMARY)
        out_rel = relationship or _OP_TO_RELATIONSHIP.get(operation, EdgeRelationship.DERIVED_FROM)
        meta = {
            "operation": operation.value,
            "instrumentation": instrumentation,
            **(metadata or {}),
        }

        out = ProvenanceSpan(
            origin=least_trust,
            kind=out_kind,
            source="transformation",
            content_hash=content_hash(output_content),
            content_redacted=redact_sensitive(output_content),
            parent_ids=list(input_span_ids),
            agent_id=agent_id,
            provenance_status=status,
            metadata=meta,
        )
        self.register_span(out)
        for input_id in input_span_ids:
            self.link(
                src_span_id=input_id,
                dst_span_id=out.span_id,
                relationship=out_rel,
                evidence_type=EvidenceType.EXPLICIT,
            )
        record = TransformationRecord(
            operation=operation,
            input_span_ids=list(input_span_ids),
            output_span_id=out.span_id,
            agent_id=agent_id,
            model=model,
            instrumentation=instrumentation,
        )
        self.store.put_transformation(record)
        return out, record

    def record_gap(
        self,
        *,
        reason: str,
        output_content: str,
        claimed_parent_ids: list[str] | None = None,
        agent_id: str | None = None,
        model: str | None = None,
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        """Mark a missing instrumentation boundary.

        Gap spans are never KNOWN. Present claimed parents are linked with GAP_FROM;
        missing claims are recorded in metadata without inventing nodes.
        """
        claimed = list(claimed_parent_ids or [])
        present = [pid for pid in claimed if self.store.get_span(pid) is not None]
        missing = [pid for pid in claimed if pid not in present]

        if present and not missing:
            status = ProvenanceStatus.PARTIAL
            origin = self._least_trust_origin(present)
        elif present and missing:
            status = ProvenanceStatus.PARTIAL
            origin = Origin.UNKNOWN
        else:
            status = ProvenanceStatus.UNKNOWN
            origin = Origin.UNKNOWN

        gap = ProvenanceSpan(
            origin=origin,
            kind=SpanKind.GAP,
            source="untracked",
            content_hash=content_hash(output_content),
            content_redacted=redact_sensitive(output_content),
            parent_ids=present,
            agent_id=agent_id,
            provenance_status=status,
            metadata={
                "reason": reason,
                "claimed_parent_ids": claimed,
                "missing_parent_ids": missing,
                "operation": TransformationOperation.UNTRACKED.value,
            },
        )
        self.register_span(gap)
        for parent_id in present:
            self.link(
                src_span_id=parent_id,
                dst_span_id=gap.span_id,
                relationship=EdgeRelationship.GAP_FROM,
                evidence_type=EvidenceType.EXPLICIT,
                metadata={"gap_reason": reason},
            )
        record = TransformationRecord(
            operation=TransformationOperation.UNTRACKED,
            input_span_ids=present,
            output_span_id=gap.span_id,
            agent_id=agent_id,
            model=model,
            instrumentation="NONE",
        )
        self.store.put_transformation(record)
        return gap, record

    def transfer_to_agent(
        self,
        *,
        sender_agent: str,
        recipient_agent: str,
        content: str,
        parent_span_ids: list[str],
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        """Cross-agent transfer with verified parents, or a gap if lineage is missing."""
        if not parent_span_ids:
            return self.record_gap(
                reason="delegation_without_parents",
                output_content=content,
                claimed_parent_ids=[],
                agent_id=recipient_agent,
            )
        missing = [p for p in parent_span_ids if self.store.get_span(p) is None]
        if missing:
            return self.record_gap(
                reason="delegation_missing_parents",
                output_content=content,
                claimed_parent_ids=parent_span_ids,
                agent_id=recipient_agent,
            )
        return self.record_transformation(
            operation=TransformationOperation.AGENT_DELEGATION,
            input_span_ids=parent_span_ids,
            output_content=content,
            agent_id=recipient_agent,
            kind=SpanKind.AGENT_MESSAGE,
            relationship=EdgeRelationship.TRANSFERRED_TO_AGENT,
            instrumentation="SDK",
            metadata={
                "sender_agent": sender_agent,
                "recipient_agent": recipient_agent,
            },
        )

    def store_in_memory(
        self,
        *,
        parent_span_id: str,
        key: str,
        agent_id: str | None = None,
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        parent = self.store.get_span(parent_span_id)
        if parent is None:
            raise ValueError(f"unknown parent span: {parent_span_id}")
        content = parent.content_redacted or parent.content_hash
        return self.record_transformation(
            operation=TransformationOperation.MEMORY_STORE,
            input_span_ids=[parent_span_id],
            output_content=f"memory:{key}:{content}",
            agent_id=agent_id or parent.agent_id,
            kind=SpanKind.MEMORY,
            relationship=EdgeRelationship.STORED_IN_MEMORY,
            metadata={"memory_key": key},
        )

    def retrieve_from_memory(
        self,
        *,
        memory_span_id: str,
        agent_id: str | None = None,
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        memory = self.store.get_span(memory_span_id)
        if memory is None:
            raise ValueError(f"unknown memory span: {memory_span_id}")
        content = memory.content_redacted or memory.content_hash
        return self.record_transformation(
            operation=TransformationOperation.MEMORY_RETRIEVE,
            input_span_ids=[memory_span_id],
            output_content=f"recall:{content}",
            agent_id=agent_id or memory.agent_id,
            kind=SpanKind.MEMORY,
            relationship=EdgeRelationship.RETRIEVED_FROM_MEMORY,
            metadata={"memory_key": memory.metadata.get("memory_key")},
        )

    def attach_inferred_link(
        self,
        *,
        src_span_id: str,
        output_content: str,
        relationship: EdgeRelationship = EdgeRelationship.USED_IN_TOOL_ARGUMENT,
        agent_id: str | None = None,
        note: str = "reconstruction_placeholder",
    ) -> ProvenanceSpan:
        """Create an INFERRED span for future reconstruction — never upgrades to KNOWN."""
        if self.store.get_span(src_span_id) is None:
            raise ValueError(f"unknown src span: {src_span_id}")
        inferred = ProvenanceSpan(
            origin=Origin.UNKNOWN,
            kind=SpanKind.TOOL_ARG,
            source="reconstruction",
            content_hash=content_hash(output_content),
            content_redacted=redact_sensitive(output_content),
            parent_ids=[src_span_id],
            agent_id=agent_id,
            provenance_status=ProvenanceStatus.INFERRED,
            confidence=None,
            metadata={"note": note},
        )
        self.register_span(inferred)
        self.link(
            src_span_id=src_span_id,
            dst_span_id=inferred.span_id,
            relationship=relationship,
            evidence_type=EvidenceType.INFERRED,
            metadata={"note": note},
        )
        return inferred

    def ancestors(self, span_id: str) -> list[ProvenanceSpan]:
        spans: list[ProvenanceSpan] = []
        for sid in self.graph.ancestors(span_id):
            span = self.store.get_span(sid)
            if span is not None:
                spans.append(span)
        return spans

    def transformation_chain(self, span_id: str) -> list[ProvenanceSpan]:
        chain: list[ProvenanceSpan] = []
        for sid in self.graph.transformation_chain(span_id):
            span = self.store.get_span(sid)
            if span is not None:
                chain.append(span)
        return chain

    def lineage_completeness(self, span_id: str) -> LineageCompleteness:
        return analyze_completeness(self.store, self.graph, span_id)

    def origin_conflicts(self, span_id: str) -> OriginConflict:
        return detect_origin_conflicts(self.store, self.graph, span_id)

    def validate(self) -> list[str]:
        return self.graph.validate_integrity()
