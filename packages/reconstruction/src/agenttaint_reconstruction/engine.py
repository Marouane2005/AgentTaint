"""Reconstruction engine: multi-channel evidence → INFERRED provenance only."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from agenttaint_core.schemas import (
    ArgumentEvidence,
    EdgeRelationship,
    Origin,
    ProvenanceSpan,
    ProvenanceStatus,
)
from agenttaint_provenance.registry import ProvenanceRegistry

from agenttaint_reconstruction.aggregate import (
    ChannelEvidence,
    SupportLevel,
    support_level,
    to_argument_evidence,
)
from agenttaint_reconstruction.lexical import lexical_similarity
from agenttaint_reconstruction.semantic import (
    EmbeddingBackend,
    semantic_similarity,
    try_create_default_semantic_backend,
)
from agenttaint_reconstruction.structural import structural_matches


class AblationMode(StrEnum):
    LEXICAL = "lexical"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    EXPLICIT = "explicit"
    COMBINED = "combined"
    LEXICAL_STRUCTURAL = "lexical_structural"


@dataclass(frozen=True)
class CandidateRecord:
    """Text corpus entry for reconstruction (keeps plaintext out of audit DB)."""

    span_id: str
    text: str
    origin: Origin = Origin.UNTRUSTED_TOOL
    agent_id: str | None = None
    provenance_status: ProvenanceStatus = ProvenanceStatus.KNOWN


@dataclass
class MatchResult:
    candidate: CandidateRecord
    channel: ChannelEvidence
    level: SupportLevel
    evidence: ArgumentEvidence


@dataclass
class ReconstructionResult:
    argument_name: str
    argument_value_preview: str
    ablation_mode: AblationMode
    matches: list[MatchResult] = field(default_factory=list)
    inferred_spans: list[ProvenanceSpan] = field(default_factory=list)
    effective_status: ProvenanceStatus = ProvenanceStatus.UNKNOWN
    notes: list[str] = field(default_factory=list)
    semantic_available: bool = False

    @property
    def best_match(self) -> MatchResult | None:
        if not self.matches:
            return None
        order = {
            SupportLevel.STRONG: 3,
            SupportLevel.MODERATE: 2,
            SupportLevel.WEAK: 1,
            SupportLevel.NONE: 0,
        }
        return max(self.matches, key=lambda m: (order[m.level], m.channel.lexical_score))


def _channels_enabled(mode: AblationMode) -> set[str]:
    if mode == AblationMode.COMBINED:
        return {"lexical", "structural", "semantic", "explicit"}
    if mode == AblationMode.LEXICAL_STRUCTURAL:
        return {"lexical", "structural", "explicit"}
    return {mode.value}


def _support_rank(level: SupportLevel) -> int:
    return {
        SupportLevel.NONE: 0,
        SupportLevel.WEAK: 1,
        SupportLevel.MODERATE: 2,
        SupportLevel.STRONG: 3,
    }[level]


class ReconstructionEngine:
    """Rebuild *possible* influence links without claiming verified causation."""

    def __init__(
        self,
        registry: ProvenanceRegistry,
        *,
        embedding_backend: EmbeddingBackend | None | object = ...,
        lexical_threshold: float = 0.55,
        semantic_threshold: float = 0.70,
        min_support_to_attach: SupportLevel = SupportLevel.WEAK,
    ) -> None:
        self.registry = registry
        self.lexical_threshold = lexical_threshold
        self.semantic_threshold = semantic_threshold
        self.min_support_to_attach = min_support_to_attach
        if embedding_backend is ...:
            self.embedding_backend = try_create_default_semantic_backend()
        else:
            self.embedding_backend = embedding_backend  # type: ignore[assignment]

    def reconstruct_argument(
        self,
        *,
        argument_name: str,
        argument_value: str,
        candidates: Iterable[CandidateRecord],
        ablation: AblationMode = AblationMode.COMBINED,
        agent_id: str | None = None,
        attach: bool = True,
        max_attachments: int = 3,
        explicit_source_ids: Iterable[str] | None = None,
        context_span_id: str | None = None,
    ) -> ReconstructionResult:
        """Score candidates and optionally attach INFERRED USED_IN_TOOL_ARGUMENT edges.

        Parameters
        ----------
        explicit_source_ids:
            Spans already known (via SDK) to be in the argument's lineage.
        context_span_id:
            If set, a candidate counts as explicit when an EXPLICIT graph path
            exists from the candidate to this span.
        """
        enabled = _channels_enabled(ablation)
        explicit_ids = set(explicit_source_ids or [])
        notes: list[str] = [
            "Similarity/support scores are evidence signals, not P(causation).",
            f"Ablation mode: {ablation.value}",
        ]
        semantic_available = self.embedding_backend is not None
        if "semantic" in enabled and not semantic_available:
            notes.append("Semantic channel requested but no embedding backend is available.")

        matches: list[MatchResult] = []
        for candidate in candidates:
            channel = self._score_candidate(
                argument_value=argument_value,
                candidate=candidate,
                enabled=enabled,
                explicit_ids=explicit_ids,
                context_span_id=context_span_id,
            )
            level = support_level(
                lexical_score=channel.lexical_score if "lexical" in enabled else 0.0,
                structural_match=channel.structural_match if "structural" in enabled else False,
                semantic_score=channel.semantic_score if "semantic" in enabled else None,
                explicit_lineage=channel.explicit_lineage if "explicit" in enabled else False,
                lexical_threshold=self.lexical_threshold,
                semantic_threshold=self.semantic_threshold,
            )
            if enabled == {"explicit"} and not channel.explicit_lineage:
                level = SupportLevel.NONE
            if level == SupportLevel.NONE:
                continue
            evidence = to_argument_evidence(
                argument_name=argument_name,
                argument_value=argument_value,
                channel=channel,
                level=level,
            )
            matches.append(
                MatchResult(
                    candidate=candidate,
                    channel=channel,
                    level=level,
                    evidence=evidence,
                )
            )

        matches.sort(
            key=lambda m: (
                _support_rank(m.level),
                m.channel.lexical_score,
                1 if m.channel.structural_match else 0,
            ),
            reverse=True,
        )

        inferred_spans: list[ProvenanceSpan] = []
        attachable = [
            m
            for m in matches
            if _support_rank(m.level) >= _support_rank(self.min_support_to_attach)
        ]
        if attach:
            for match in attachable[:max_attachments]:
                span = self.registry.attach_inferred_link(
                    src_span_id=match.candidate.span_id,
                    output_content=argument_value,
                    relationship=EdgeRelationship.USED_IN_TOOL_ARGUMENT,
                    agent_id=agent_id,
                    note=(
                        f"reconstructed:{ablation.value}:{match.level.value}:"
                        f"lex={match.channel.lexical_score:.3f}:"
                        f"struct={match.channel.structural_match}"
                    ),
                )
                if span.provenance_status != ProvenanceStatus.INFERRED:
                    raise RuntimeError("reconstruction must only create INFERRED spans")
                inferred_spans.append(span)

        if matches or inferred_spans:
            effective = ProvenanceStatus.INFERRED
        else:
            effective = ProvenanceStatus.UNKNOWN
            notes.append("Insufficient evidence; leaving provenance UNKNOWN.")

        preview = argument_value if len(argument_value) <= 64 else argument_value[:61] + "..."
        return ReconstructionResult(
            argument_name=argument_name,
            argument_value_preview=preview,
            ablation_mode=ablation,
            matches=matches,
            inferred_spans=inferred_spans,
            effective_status=effective,
            notes=notes,
            semantic_available=semantic_available,
        )

    def _score_candidate(
        self,
        *,
        argument_value: str,
        candidate: CandidateRecord,
        enabled: set[str],
        explicit_ids: set[str],
        context_span_id: str | None,
    ) -> ChannelEvidence:
        channel = ChannelEvidence(span_id=candidate.span_id)
        if "lexical" in enabled:
            channel.lexical = lexical_similarity(argument_value, candidate.text)
        if "structural" in enabled:
            channel.structural_hits = structural_matches(argument_value, candidate.text)
        if "semantic" in enabled:
            channel.semantic = semantic_similarity(
                argument_value, candidate.text, self.embedding_backend
            )
        if "explicit" in enabled:
            channel.explicit_lineage = candidate.span_id in explicit_ids
            if (
                not channel.explicit_lineage
                and context_span_id is not None
                and self.registry.graph.has_node(candidate.span_id)
                and self.registry.graph.has_node(context_span_id)
            ):
                channel.explicit_lineage = self.registry.graph.only_explicit_path_exists(
                    candidate.span_id, context_span_id
                )
        return channel
