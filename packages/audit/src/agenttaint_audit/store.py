"""Persist ToolCallDecision records (hashes/redaction by default)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agenttaint_core.schemas import (
    ArgumentEvidence,
    DecisionOutcome,
    EvidenceType,
    ProvenanceStatus,
    RiskTier,
    ToolCallDecision,
)
from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class DecisionRow(Base):
    __tablename__ = "tool_call_decisions"

    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_redacted_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    provenance_status: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def _to_row(decision: ToolCallDecision) -> DecisionRow:
    return DecisionRow(
        call_id=decision.call_id,
        agent_id=decision.agent_id,
        tool_name=decision.tool,
        risk_tier=decision.risk_tier.value,
        arguments_hash=decision.arguments_hash,
        arguments_redacted_json=dict(decision.arguments_redacted),
        evidence_json=[e.model_dump(mode="json") for e in decision.evidence],
        provenance_status=decision.provenance_status.value,
        decision=decision.decision.value,
        policy_id=decision.policy_id,
        explanation=decision.explanation,
        latency_ms=decision.latency_ms,
        created_at=decision.created_at,
        schema_version=decision.schema_version,
    )


def _from_row(row: DecisionRow) -> ToolCallDecision:
    evidence: list[ArgumentEvidence] = []
    for item in row.evidence_json or []:
        evidence.append(
            ArgumentEvidence(
                argument_name=item["argument_name"],
                value_hash=item["value_hash"],
                lexical_score=float(item.get("lexical_score", 0.0)),
                semantic_score=float(item.get("semantic_score", 0.0)),
                structural_match=bool(item.get("structural_match", False)),
                explicit_lineage=bool(item.get("explicit_lineage", False)),
                matched_source_ids=list(item.get("matched_source_ids") or []),
                evidence_type=EvidenceType(item.get("evidence_type", "INFERRED")),
                confidence=item.get("confidence"),
                provenance_status=ProvenanceStatus(
                    item.get("provenance_status", "UNKNOWN")
                ),
            )
        )
    return ToolCallDecision(
        call_id=row.call_id,
        agent_id=row.agent_id,
        tool=row.tool_name,
        risk_tier=RiskTier(row.risk_tier),
        arguments_hash=row.arguments_hash,
        arguments_redacted=dict(row.arguments_redacted_json or {}),
        evidence=evidence,
        provenance_status=ProvenanceStatus(row.provenance_status),
        decision=DecisionOutcome(row.decision),
        policy_id=row.policy_id,
        explanation=row.explanation,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
        schema_version=row.schema_version,
    )


class AuditStore:
    def __init__(self, database_url: str = "sqlite+pysqlite:///:memory:") -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def record(self, decision: ToolCallDecision) -> ToolCallDecision:
        with self.session() as session:
            session.add(_to_row(decision))
            session.commit()
        return decision

    def get(self, call_id: str) -> ToolCallDecision | None:
        with self.session() as session:
            row = session.get(DecisionRow, call_id)
            return _from_row(row) if row else None

    def list_decisions(self, *, limit: int = 100) -> list[ToolCallDecision]:
        with self.session() as session:
            rows = session.scalars(
                select(DecisionRow).order_by(DecisionRow.created_at.desc()).limit(limit)
            ).all()
            return [_from_row(r) for r in rows]

    def count_by_decision(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for decision in self.list_decisions(limit=10_000):
            key = decision.decision.value
            counts[key] = counts.get(key, 0) + 1
        return counts
