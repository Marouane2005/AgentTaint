"""SQLAlchemy-backed durable provenance store (SQLite / Postgres)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class SpanRow(Base):
    __tablename__ = "provenance_spans"

    span_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    parent_ids_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EdgeRow(Base):
    __tablename__ = "provenance_edges"

    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    src_span_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("provenance_spans.span_id"), index=True
    )
    dst_span_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("provenance_spans.span_id"), index=True
    )
    relationship: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TransformationRow(Base):
    __tablename__ = "transformations"

    transformation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    output_span_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_span_ids_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instrumentation: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def _span_to_row(span: ProvenanceSpan) -> SpanRow:
    return SpanRow(
        span_id=span.span_id,
        origin=span.origin.value,
        kind=span.kind.value,
        source_tool=span.source,
        agent_id=span.agent_id,
        content_hash=span.content_hash,
        content_redacted=span.content_redacted,
        embedding_id=span.embedding_ref,
        provenance_status=span.provenance_status.value,
        confidence=span.confidence,
        parent_ids_json=list(span.parent_ids),
        metadata_json=dict(span.metadata),
        created_at=span.created_at,
        schema_version=span.schema_version,
    )


def _row_to_span(row: SpanRow) -> ProvenanceSpan:
    return ProvenanceSpan(
        span_id=row.span_id,
        origin=Origin(row.origin),
        kind=SpanKind(row.kind),
        source=row.source_tool,
        content_hash=row.content_hash,
        content_redacted=row.content_redacted,
        embedding_ref=row.embedding_id,
        provenance_status=ProvenanceStatus(row.provenance_status),
        confidence=row.confidence,
        parent_ids=list(row.parent_ids_json or []),
        agent_id=row.agent_id,
        metadata=dict(row.metadata_json or {}),
        created_at=row.created_at,
        schema_version=row.schema_version,
    )


def _edge_to_row(edge: ProvenanceEdge) -> EdgeRow:
    return EdgeRow(
        edge_id=edge.edge_id,
        src_span_id=edge.src_span_id,
        dst_span_id=edge.dst_span_id,
        relationship=edge.relationship.value,
        evidence_type=edge.evidence_type.value,
        metadata_json=dict(edge.metadata),
        created_at=edge.created_at,
        schema_version=edge.schema_version,
    )


def _row_to_edge(row: EdgeRow) -> ProvenanceEdge:
    return ProvenanceEdge(
        edge_id=row.edge_id,
        src_span_id=row.src_span_id,
        dst_span_id=row.dst_span_id,
        relationship=EdgeRelationship(row.relationship),
        evidence_type=EvidenceType(row.evidence_type),
        metadata=dict(row.metadata_json or {}),
        created_at=row.created_at,
        schema_version=row.schema_version,
    )


class ProvenanceStore:
    """Persistent provenance records. Fails loudly on integrity problems."""

    def __init__(self, database_url: str = "sqlite+pysqlite:///:memory:") -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def put_span(self, span: ProvenanceSpan) -> ProvenanceSpan:
        with self.session() as session:
            existing = session.get(SpanRow, span.span_id)
            if existing is not None:
                raise ValueError(f"span already exists: {span.span_id}")
            session.add(_span_to_row(span))
            session.commit()
        return span

    def get_span(self, span_id: str) -> ProvenanceSpan | None:
        with self.session() as session:
            row = session.get(SpanRow, span_id)
            return _row_to_span(row) if row else None

    def put_edge(self, edge: ProvenanceEdge) -> ProvenanceEdge:
        with self.session() as session:
            if session.get(SpanRow, edge.src_span_id) is None:
                raise ValueError(f"missing src span: {edge.src_span_id}")
            if session.get(SpanRow, edge.dst_span_id) is None:
                raise ValueError(f"missing dst span: {edge.dst_span_id}")
            if edge.evidence_type == EvidenceType.INFERRED:
                # Allowed, but never implies KNOWN status on either endpoint by itself.
                pass
            session.add(_edge_to_row(edge))
            session.commit()
        return edge

    def list_edges(self) -> list[ProvenanceEdge]:
        with self.session() as session:
            rows = session.scalars(select(EdgeRow)).all()
            return [_row_to_edge(r) for r in rows]

    def edges_from(self, span_id: str) -> list[ProvenanceEdge]:
        with self.session() as session:
            rows = session.scalars(select(EdgeRow).where(EdgeRow.src_span_id == span_id)).all()
            return [_row_to_edge(r) for r in rows]

    def edges_to(self, span_id: str) -> list[ProvenanceEdge]:
        with self.session() as session:
            rows = session.scalars(select(EdgeRow).where(EdgeRow.dst_span_id == span_id)).all()
            return [_row_to_edge(r) for r in rows]

    def put_transformation(self, record: TransformationRecord) -> TransformationRecord:
        with self.session() as session:
            if session.get(SpanRow, record.output_span_id) is None:
                raise ValueError(f"missing output span: {record.output_span_id}")
            for input_id in record.input_span_ids:
                if session.get(SpanRow, input_id) is None:
                    raise ValueError(f"missing input span: {input_id}")
            session.add(
                TransformationRow(
                    transformation_id=record.transformation_id,
                    operation=record.operation.value,
                    output_span_id=record.output_span_id,
                    input_span_ids_json=list(record.input_span_ids),
                    agent_id=record.agent_id,
                    model=record.model,
                    instrumentation=record.instrumentation,
                    created_at=record.created_at,
                    schema_version=record.schema_version,
                )
            )
            session.commit()
        return record

    def get_transformation(self, transformation_id: str) -> TransformationRecord | None:
        with self.session() as session:
            row = session.get(TransformationRow, transformation_id)
            if row is None:
                return None
            return TransformationRecord(
                transformation_id=row.transformation_id,
                operation=TransformationOperation(row.operation),
                input_span_ids=list(row.input_span_ids_json or []),
                output_span_id=row.output_span_id,
                agent_id=row.agent_id,
                model=row.model,
                instrumentation=row.instrumentation,
                created_at=row.created_at,
                schema_version=row.schema_version,
            )

    def list_spans(self) -> list[ProvenanceSpan]:
        with self.session() as session:
            rows = session.scalars(select(SpanRow)).all()
            return [_row_to_span(r) for r in rows]

    def verify_content_hash(self, span_id: str, content: str) -> bool:
        span = self.get_span(span_id)
        if span is None:
            return False
        from agenttaint_core.hashing import content_hash

        return span.content_hash == content_hash(content)
