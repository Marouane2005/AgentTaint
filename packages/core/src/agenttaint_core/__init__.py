"""AgentTaint core types and utilities."""

from agenttaint_core.crypto import generate_nonce, hmac_sign, hmac_verify
from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    SCHEMA_VERSION,
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

__all__ = [
    "SCHEMA_VERSION",
    "EdgeRelationship",
    "EvidenceType",
    "LineageCompleteness",
    "Origin",
    "OriginConflict",
    "ProvenanceEdge",
    "ProvenanceSpan",
    "ProvenanceStatus",
    "SpanKind",
    "TransformationOperation",
    "TransformationRecord",
    "content_hash",
    "generate_nonce",
    "hmac_sign",
    "hmac_verify",
    "redact_sensitive",
]

__version__ = "1.0.0"
