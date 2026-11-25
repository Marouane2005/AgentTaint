"""Transparent evidence aggregation.

Does NOT produce calibrated probabilities of causation.
Reports per-channel scores and a heuristic support level for policy scrutiny.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from agenttaint_core.hashing import content_hash
from agenttaint_core.schemas import (
    ArgumentEvidence,
    EvidenceType,
    ProvenanceStatus,
)

from agenttaint_reconstruction.lexical import LexicalScore
from agenttaint_reconstruction.semantic import SemanticScore
from agenttaint_reconstruction.structural import StructuralHit


class SupportLevel(StrEnum):
    """Ordinal support for scrutiny — not a probability."""

    NONE = "NONE"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


@dataclass
class ChannelEvidence:
    span_id: str
    lexical: LexicalScore | None = None
    structural_hits: list[StructuralHit] = field(default_factory=list)
    semantic: SemanticScore | None = None
    explicit_lineage: bool = False
    # True when the argument is a high-precision structured value (email, URL, path,
    # shell command) and semantic similarity was ignored for lack of corroboration.
    semantic_suppressed: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def structural_match(self) -> bool:
        return bool(self.structural_hits)

    @property
    def lexical_score(self) -> float:
        return 0.0 if self.lexical is None else self.lexical.score

    @property
    def semantic_score(self) -> float | None:
        if self.semantic is None or not self.semantic.available:
            return None
        return self.semantic.cosine


def support_level(
    *,
    lexical_score: float,
    structural_match: bool,
    semantic_score: float | None,
    explicit_lineage: bool,
    lexical_threshold: float = 0.55,
    semantic_threshold: float = 0.70,
    semantic_requires_corroboration: bool = False,
    corroborated: bool = False,
) -> SupportLevel:
    """Ordinal support level.

    ``semantic_requires_corroboration`` marks high-precision structured arguments
    (emails, URLs, paths, shell commands). For those, a high cosine score alone is
    ignored; it only counts when ``corroborated`` (weak structural/domain overlap
    or explicit session context) is also true.
    """
    if semantic_requires_corroboration and not (corroborated or explicit_lineage):
        semantic_score = None
    if explicit_lineage and (structural_match or lexical_score >= lexical_threshold):
        return SupportLevel.STRONG
    if structural_match and lexical_score >= lexical_threshold:
        return SupportLevel.STRONG
    if structural_match:
        return SupportLevel.MODERATE
    if semantic_score is not None and semantic_score >= semantic_threshold:
        if lexical_score >= 0.35:
            return SupportLevel.MODERATE
        return SupportLevel.WEAK
    if lexical_score >= lexical_threshold:
        return SupportLevel.WEAK
    return SupportLevel.NONE


def to_argument_evidence(
    *,
    argument_name: str,
    argument_value: str,
    channel: ChannelEvidence,
    level: SupportLevel,
) -> ArgumentEvidence:
    """Build ArgumentEvidence. confidence stays null (uncalibrated)."""
    # Reconstruction only ever emits INFERRED (explicit_lineage is a separate signal).
    status = ProvenanceStatus.UNKNOWN if level == SupportLevel.NONE else ProvenanceStatus.INFERRED

    return ArgumentEvidence(
        argument_name=argument_name,
        value_hash=content_hash(argument_value),
        lexical_score=channel.lexical_score,
        semantic_score=(
            0.0
            if channel.semantic_score is None or channel.semantic_suppressed
            else float(channel.semantic_score)
        ),
        structural_match=channel.structural_match,
        explicit_lineage=channel.explicit_lineage,
        matched_source_ids=[channel.span_id] if level != SupportLevel.NONE else [],
        # Reconstruction always emits INFERRED; explicit_lineage is a separate signal.
        evidence_type=EvidenceType.INFERRED,
        confidence=None,  # intentionally uncalibrated — not P(causation)
        provenance_status=status,
    )
