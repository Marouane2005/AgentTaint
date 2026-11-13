"""High-level provenance registry used by the proxy and SDK."""

from __future__ import annotations

from pathlib import Path

from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    EdgeRelationship,
    EvidenceType,
    Origin,
    ProvenanceEdge,
    ProvenanceSpan,
    ProvenanceStatus,
    SpanKind,
    TransformationOperation,
    TransformationRecord,
)

from agenttaint_provenance.graph import ProvenanceGraph
from agenttaint_provenance.labeler import SourceLabeler
from agenttaint_provenance.store import ProvenanceStore
from agenttaint_provenance.trust import TrustRegistry, load_trust_registry

_ORIGIN_RANK = {
    Origin.USER: 0,
    Origin.TRUSTED_TOOL: 1,
    Origin.INTERNAL: 2,
    Origin.UNTRUSTED_TOOL: 3,
    Origin.UNKNOWN: 4,
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
        metadata: dict | None = None,
    ) -> ProvenanceEdge:
        if evidence_type == EvidenceType.INFERRED:
            dst = self.store.get_span(dst_span_id)
            if dst is not None and dst.provenance_status == ProvenanceStatus.KNOWN:
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

    def record_transformation(
        self,
        *,
        operation: TransformationOperation,
        input_span_ids: list[str],
        output_content: str,
        agent_id: str | None = None,
        model: str | None = None,
        kind: SpanKind = SpanKind.SUMMARY,
        relationship: EdgeRelationship = EdgeRelationship.SUMMARIZED_FROM,
        instrumentation: str = "SDK",
    ) -> tuple[ProvenanceSpan, TransformationRecord]:
        if not input_span_ids:
            raise ValueError("transformations require at least one input span")
        for input_id in input_span_ids:
            if self.store.get_span(input_id) is None:
                raise ValueError(f"unknown input span: {input_id}")

        status = (
            ProvenanceStatus.KNOWN if instrumentation == "SDK" else ProvenanceStatus.PARTIAL
        )
        least_trust = Origin.USER
        for input_id in input_span_ids:
            parent = self.store.get_span(input_id)
            assert parent is not None
            if _ORIGIN_RANK[parent.origin] > _ORIGIN_RANK[least_trust]:
                least_trust = parent.origin

        out = ProvenanceSpan(
            origin=least_trust,
            kind=kind,
            source="transformation",
            content_hash=content_hash(output_content),
            content_redacted=redact_sensitive(output_content),
            parent_ids=list(input_span_ids),
            agent_id=agent_id,
            provenance_status=status,
            metadata={"operation": operation.value},
        )
        self.register_span(out)
        for input_id in input_span_ids:
            self.link(
                src_span_id=input_id,
                dst_span_id=out.span_id,
                relationship=relationship,
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

    def ancestors(self, span_id: str) -> list[ProvenanceSpan]:
        spans: list[ProvenanceSpan] = []
        for sid in self.graph.ancestors(span_id):
            span = self.store.get_span(sid)
            if span is not None:
                spans.append(span)
        return spans

    def validate(self) -> list[str]:
        return self.graph.validate_integrity()
