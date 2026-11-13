"""Versioned provenance and evidence schemas.

KNOWN provenance is never silently upgraded from INFERRED evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid4())


class Origin(StrEnum):
    USER = "USER"
    TRUSTED_TOOL = "TRUSTED_TOOL"
    UNTRUSTED_TOOL = "UNTRUSTED_TOOL"
    INTERNAL = "INTERNAL"
    UNKNOWN = "UNKNOWN"


class ProvenanceStatus(StrEnum):
    KNOWN = "KNOWN"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"


class SpanKind(StrEnum):
    SOURCE = "SOURCE"
    EXTRACT = "EXTRACT"
    SUMMARY = "SUMMARY"
    REWRITE = "REWRITE"
    MEMORY = "MEMORY"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    TOOL_ARG = "TOOL_ARG"
    TOOL_RESULT = "TOOL_RESULT"
    USER_INSTRUCTION = "USER_INSTRUCTION"
    GAP = "GAP"


class EdgeRelationship(StrEnum):
    EXTRACTED_FROM = "EXTRACTED_FROM"
    SUMMARIZED_FROM = "SUMMARIZED_FROM"
    REWRITTEN_FROM = "REWRITTEN_FROM"
    STORED_IN_MEMORY = "STORED_IN_MEMORY"
    RETRIEVED_FROM_MEMORY = "RETRIEVED_FROM_MEMORY"
    TRANSFERRED_TO_AGENT = "TRANSFERRED_TO_AGENT"
    DERIVED_FROM = "DERIVED_FROM"
    USED_IN_TOOL_ARGUMENT = "USED_IN_TOOL_ARGUMENT"
    GAP_FROM = "GAP_FROM"


class EvidenceType(StrEnum):
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"


class TransformationOperation(StrEnum):
    SUMMARIZATION = "SUMMARIZATION"
    REWRITE = "REWRITE"
    PARAPHRASE = "PARAPHRASE"
    EXTRACTION = "EXTRACTION"
    MEMORY_STORE = "MEMORY_STORE"
    MEMORY_RETRIEVE = "MEMORY_RETRIEVE"
    AGENT_DELEGATION = "AGENT_DELEGATION"
    TOOL_RESULT = "TOOL_RESULT"
    UNTRACKED = "UNTRACKED"


class RiskTier(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DecisionOutcome(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CONFIRM = "CONFIRM"


class ProvenanceSpan(BaseModel):
    span_id: str = Field(default_factory=_new_id)
    origin: Origin
    kind: SpanKind = SpanKind.SOURCE
    source: str | None = None
    content_hash: str
    created_at: datetime = Field(default_factory=_utcnow)
    parent_ids: list[str] = Field(default_factory=list)
    agent_id: str | None = None
    confidence: float | None = None
    provenance_status: ProvenanceStatus = ProvenanceStatus.KNOWN
    embedding_ref: str | None = None
    content_redacted: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return value

    @field_validator("provenance_status")
    @classmethod
    def _known_has_no_required_confidence(
        cls, value: ProvenanceStatus, info: Any
    ) -> ProvenanceStatus:
        # Explicit KNOWN spans should not pretend to be probabilistic.
        return value


class ProvenanceEdge(BaseModel):
    edge_id: str = Field(default_factory=_new_id)
    src_span_id: str
    dst_span_id: str
    relationship: EdgeRelationship
    evidence_type: EvidenceType = EvidenceType.EXPLICIT
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


class TransformationRecord(BaseModel):
    transformation_id: str = Field(default_factory=_new_id)
    operation: TransformationOperation
    input_span_ids: list[str] = Field(default_factory=list)
    output_span_id: str
    agent_id: str | None = None
    model: str | None = None
    instrumentation: str = "SDK"
    created_at: datetime = Field(default_factory=_utcnow)
    schema_version: int = SCHEMA_VERSION


class ArgumentEvidence(BaseModel):
    argument_name: str
    value_hash: str
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    structural_match: bool = False
    explicit_lineage: bool = False
    matched_source_ids: list[str] = Field(default_factory=list)
    evidence_type: EvidenceType = EvidenceType.INFERRED
    confidence: float | None = None
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNKNOWN


class ToolCallDecision(BaseModel):
    call_id: str = Field(default_factory=_new_id)
    agent_id: str | None = None
    tool: str
    risk_tier: RiskTier
    arguments_hash: str
    arguments_redacted: dict[str, Any] = Field(default_factory=dict)
    evidence: list[ArgumentEvidence] = Field(default_factory=list)
    provenance_status: ProvenanceStatus = ProvenanceStatus.UNKNOWN
    decision: DecisionOutcome
    policy_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    latency_ms: int = 0
    explanation: str | None = None
    schema_version: int = SCHEMA_VERSION
