"""In-memory provenance graph over the durable store (NetworkX)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import networkx as nx
from agenttaint_core.schemas import (
    EvidenceType,
    ProvenanceEdge,
    ProvenanceSpan,
    ProvenanceStatus,
    SpanKind,
)

from agenttaint_provenance.store import ProvenanceStore


class ProvenanceGraph:
    """Directed graph: edge src → dst means dst was derived from / influenced by src."""

    def __init__(self, store: ProvenanceStore) -> None:
        self.store = store
        self._g: Any = nx.DiGraph()

    def rebuild(self) -> None:
        self._g.clear()
        for span in self.store.list_spans():
            self._g.add_node(span.span_id, span=span)
        for edge in self.store.list_edges():
            self._g.add_edge(
                edge.src_span_id,
                edge.dst_span_id,
                edge=edge,
                evidence_type=edge.evidence_type.value,
                relationship=edge.relationship.value,
            )

    def add_span(self, span: ProvenanceSpan) -> None:
        self._g.add_node(span.span_id, span=span)

    def add_edge(self, edge: ProvenanceEdge) -> None:
        self._g.add_edge(
            edge.src_span_id,
            edge.dst_span_id,
            edge=edge,
            evidence_type=edge.evidence_type.value,
            relationship=edge.relationship.value,
        )

    def has_node(self, span_id: str) -> bool:
        return span_id in self._g

    def get_span(self, span_id: str) -> ProvenanceSpan | None:
        node = self._g.nodes.get(span_id)
        if not node:
            return None
        span = node.get("span")
        return span if isinstance(span, ProvenanceSpan) else None

    def ancestors(self, span_id: str) -> list[str]:
        """Backward provenance: all nodes that can reach span_id (excluding self)."""
        if span_id not in self._g:
            return []
        return sorted(nx.ancestors(self._g, span_id))

    def descendants(self, span_id: str) -> list[str]:
        if span_id not in self._g:
            return []
        return sorted(nx.descendants(self._g, span_id))

    def parent_ids(self, span_id: str) -> list[str]:
        if span_id not in self._g:
            return []
        return sorted(self._g.predecessors(span_id))

    def child_ids(self, span_id: str) -> list[str]:
        if span_id not in self._g:
            return []
        return sorted(self._g.successors(span_id))

    def path_exists(self, src_id: str, dst_id: str) -> bool:
        if src_id not in self._g or dst_id not in self._g:
            return False
        return bool(nx.has_path(self._g, src_id, dst_id))

    def transformation_chain(self, span_id: str) -> list[str]:
        """Ordered path from root sources to span along explicit edges (one topo path).

        If multiple parents exist, returns a deterministic depth-first chain ending at span_id.
        """
        if span_id not in self._g:
            return []
        chain: list[str] = []
        seen: set[str] = set()

        def walk(node: str) -> None:
            if node in seen:
                return
            seen.add(node)
            for pred in sorted(self._g.predecessors(node)):
                data = self._g.get_edge_data(pred, node) or {}
                if data.get("evidence_type") != EvidenceType.EXPLICIT.value:
                    continue
                walk(pred)
            chain.append(node)

        walk(span_id)
        return chain

    def explicit_ancestors(self, span_id: str) -> list[str]:
        return self._filtered_ancestors(span_id, allowed={EvidenceType.EXPLICIT})

    def inferred_path_exists(self, src_id: str, dst_id: str) -> bool:
        """True if some path from src to dst includes at least one INFERRED edge."""
        if src_id not in self._g or dst_id not in self._g:
            return False
        if not nx.has_path(self._g, src_id, dst_id):
            return False
        for path in nx.all_simple_paths(self._g, src_id, dst_id):
            for a, b in zip(path, path[1:], strict=False):
                data = self._g.get_edge_data(a, b) or {}
                if data.get("evidence_type") == EvidenceType.INFERRED.value:
                    return True
        return False

    def only_explicit_path_exists(self, src_id: str, dst_id: str) -> bool:
        """True if there is a path using only EXPLICIT edges."""
        if src_id not in self._g or dst_id not in self._g:
            return False
        explicit_ids = set(self.explicit_ancestors(dst_id))
        explicit_ids.add(dst_id)
        return src_id in explicit_ids

    def lineage_status(self, span_id: str) -> ProvenanceStatus:
        """Conservative effective status for a span's ancestor cone."""
        span = self.get_span(span_id)
        if span is None:
            return ProvenanceStatus.UNKNOWN

        statuses = {span.provenance_status}
        for ancestor_id in self.ancestors(span_id):
            ancestor = self.get_span(ancestor_id)
            if ancestor is not None:
                statuses.add(ancestor.provenance_status)

        has_inferred_edge = False
        for node in [span_id, *self.ancestors(span_id)]:
            for pred in self._g.predecessors(node):
                data = self._g.get_edge_data(pred, node) or {}
                if data.get("evidence_type") == EvidenceType.INFERRED.value:
                    has_inferred_edge = True

        # Precedence: UNKNOWN > PARTIAL > INFERRED > KNOWN for "effective" uncertainty.
        if ProvenanceStatus.UNKNOWN in statuses:
            return ProvenanceStatus.UNKNOWN
        if ProvenanceStatus.PARTIAL in statuses:
            return ProvenanceStatus.PARTIAL
        if ProvenanceStatus.INFERRED in statuses or has_inferred_edge:
            return ProvenanceStatus.INFERRED
        return ProvenanceStatus.KNOWN

    def gap_span_ids(self, span_id: str) -> list[str]:
        gaps: list[str] = []
        for sid in [span_id, *self.ancestors(span_id)]:
            span = self.get_span(sid)
            if span is not None and span.kind == SpanKind.GAP:
                gaps.append(sid)
        return sorted(gaps)

    def validate_integrity(self) -> list[str]:
        """Return integrity problems (empty if OK). Does not mutate the graph."""
        problems: list[str] = []
        if not nx.is_directed_acyclic_graph(self._g):
            problems.append("graph contains cycles")

        for span_id, data in self._g.nodes(data=True):
            span: ProvenanceSpan | None = data.get("span")
            if span is None:
                problems.append(f"node missing span payload: {span_id}")
                continue
            for parent_id in span.parent_ids:
                if parent_id not in self._g:
                    problems.append(
                        f"span {span_id} parent_ids references missing span {parent_id}"
                    )
                elif parent_id not in set(self._g.predecessors(span_id)):
                    problems.append(
                        f"span {span_id} parent_ids missing graph edge from {parent_id}"
                    )

            if span.provenance_status == ProvenanceStatus.KNOWN and span.kind == SpanKind.GAP:
                problems.append(f"gap span {span_id} must not be marked KNOWN")

            if span.kind == SpanKind.GAP and span.provenance_status not in {
                ProvenanceStatus.PARTIAL,
                ProvenanceStatus.UNKNOWN,
            }:
                problems.append(
                    f"gap span {span_id} has invalid status {span.provenance_status.value}"
                )

        for u, v, data in self._g.edges(data=True):
            if u not in self._g.nodes or v not in self._g.nodes:
                problems.append(f"edge endpoints missing: {u} -> {v}")
                continue
            edge: ProvenanceEdge | None = data.get("edge")
            if edge is None:
                problems.append(f"edge missing payload: {u} -> {v}")
                continue
            if edge.evidence_type == EvidenceType.INFERRED:
                dst_span: ProvenanceSpan | None = self._g.nodes[v].get("span")
                if dst_span and dst_span.provenance_status == ProvenanceStatus.KNOWN:
                    explicit_preds = [
                        p
                        for p in self._g.predecessors(v)
                        if (self._g.get_edge_data(p, v) or {}).get("evidence_type")
                        == EvidenceType.EXPLICIT.value
                    ]
                    if not explicit_preds:
                        problems.append(f"span {v} marked KNOWN but has only INFERRED parents")
        return problems

    def _filtered_ancestors(self, span_id: str, allowed: Iterable[EvidenceType]) -> list[str]:
        allowed_values = {e.value for e in allowed}
        if span_id not in self._g:
            return []
        stack = [span_id]
        result: set[str] = set()
        while stack:
            current = stack.pop()
            for pred in self._g.predecessors(current):
                data = self._g.get_edge_data(pred, current) or {}
                if data.get("evidence_type") not in allowed_values:
                    continue
                if pred not in result:
                    result.add(pred)
                    stack.append(pred)
        return sorted(result)

    @property
    def node_count(self) -> int:
        return int(self._g.number_of_nodes())

    @property
    def edge_count(self) -> int:
        return int(self._g.number_of_edges())
