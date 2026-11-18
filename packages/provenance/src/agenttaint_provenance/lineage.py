"""Lineage completeness and conflict analysis for the provenance graph.

Designed so the future reconstruction engine can consume these reports without
promoting INFERRED evidence to KNOWN.
"""

from __future__ import annotations

from agenttaint_core.schemas import (
    EvidenceType,
    LineageCompleteness,
    Origin,
    OriginConflict,
    ProvenanceStatus,
    SpanKind,
)

from agenttaint_provenance.graph import ProvenanceGraph
from agenttaint_provenance.store import ProvenanceStore


def analyze_completeness(
    store: ProvenanceStore,
    graph: ProvenanceGraph,
    span_id: str,
) -> LineageCompleteness:
    span = store.get_span(span_id)
    if span is None:
        return LineageCompleteness(
            span_id=span_id,
            effective_status=ProvenanceStatus.UNKNOWN,
            is_complete=False,
            notes=["span not found"],
        )

    known: list[str] = []
    partial: list[str] = []
    inferred: list[str] = []
    unknown: list[str] = []
    gaps: list[str] = []
    untrusted: list[str] = []
    agents: set[str] = set()
    explicit_edges = 0
    inferred_edges = 0
    notes: list[str] = []

    cone = [span, *[s for sid in graph.ancestors(span_id) if (s := store.get_span(sid))]]
    for item in cone:
        if item.agent_id:
            agents.add(item.agent_id)
        if item.kind == SpanKind.GAP:
            gaps.append(item.span_id)
        if item.origin in {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN}:
            untrusted.append(item.span_id)
        if item.provenance_status == ProvenanceStatus.KNOWN:
            known.append(item.span_id)
        elif item.provenance_status == ProvenanceStatus.PARTIAL:
            partial.append(item.span_id)
        elif item.provenance_status == ProvenanceStatus.INFERRED:
            inferred.append(item.span_id)
        else:
            unknown.append(item.span_id)

        for parent_id in item.parent_ids:
            if store.get_span(parent_id) is None:
                notes.append(f"missing parent reference {parent_id} on {item.span_id}")

    for edge in store.list_edges():
        if edge.dst_span_id not in {span_id, *graph.ancestors(span_id)}:
            continue
        if edge.evidence_type == EvidenceType.EXPLICIT:
            explicit_edges += 1
        else:
            inferred_edges += 1

    effective = graph.lineage_status(span_id)
    is_complete = (
        effective == ProvenanceStatus.KNOWN
        and not gaps
        and not partial
        and not unknown
        and not inferred
        and inferred_edges == 0
        and not notes
    )
    if gaps:
        notes.append(f"{len(gaps)} gap marker(s) in ancestor cone")
    if inferred_edges:
        notes.append(f"{inferred_edges} inferred edge(s) present — not verified causation")

    return LineageCompleteness(
        span_id=span_id,
        effective_status=effective,
        is_complete=is_complete,
        known_ancestor_ids=sorted(set(known) - {span_id}),
        partial_ancestor_ids=sorted(set(partial) - {span_id}),
        inferred_ancestor_ids=sorted(set(inferred) - {span_id}),
        unknown_ancestor_ids=sorted(set(unknown) - {span_id}),
        gap_span_ids=sorted(set(gaps)),
        untrusted_source_ids=sorted(set(untrusted)),
        agent_ids=sorted(agents),
        explicit_edge_count=explicit_edges,
        inferred_edge_count=inferred_edges,
        notes=notes,
    )


def detect_origin_conflicts(
    store: ProvenanceStore,
    graph: ProvenanceGraph,
    span_id: str,
) -> OriginConflict:
    """Detect USER vs UNTRUSTED (or UNKNOWN) sources in the explicit ancestor cone."""
    span = store.get_span(span_id)
    if span is None:
        return OriginConflict(
            span_id=span_id,
            has_conflict=False,
            summary="span not found",
        )

    origins: set[Origin] = set()
    user_ids: list[str] = []
    untrusted_ids: list[str] = []
    for sid in [span_id, *graph.explicit_ancestors(span_id)]:
        item = store.get_span(sid)
        if item is None:
            continue
        origins.add(item.origin)
        if item.origin == Origin.USER:
            user_ids.append(sid)
        if item.origin in {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN}:
            untrusted_ids.append(sid)

    has_conflict = bool(user_ids) and bool(untrusted_ids)
    if has_conflict:
        summary = (
            "Explicit lineage includes both USER and UNTRUSTED/UNKNOWN sources; "
            "do not treat USER presence as authorization for untrusted-derived values."
        )
    elif untrusted_ids:
        summary = "Lineage includes untrusted or unknown sources."
    elif user_ids:
        summary = "Lineage includes user sources only (among USER/UNTRUSTED axes)."
    else:
        summary = "No USER/UNTRUSTED conflict detected."

    return OriginConflict(
        span_id=span_id,
        origins=sorted(origins, key=lambda o: o.value),
        user_span_ids=sorted(user_ids),
        untrusted_span_ids=sorted(untrusted_ids),
        has_conflict=has_conflict,
        summary=summary,
    )
