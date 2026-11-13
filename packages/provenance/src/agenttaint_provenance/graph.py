"""In-memory provenance graph over the durable store (NetworkX)."""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx
from agenttaint_core.schemas import EvidenceType, ProvenanceEdge, ProvenanceSpan, ProvenanceStatus

from agenttaint_provenance.store import ProvenanceStore


class ProvenanceGraph:
    """Directed graph: edge src → dst means dst was derived from / influenced by src."""

    def __init__(self, store: ProvenanceStore) -> None:
        self.store = store
        self._g = nx.DiGraph()

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

    def ancestors(self, span_id: str) -> list[str]:
        """Backward provenance: all nodes that can reach span_id (excluding self)."""
        if span_id not in self._g:
            return []
        nodes = nx.ancestors(self._g, span_id)
        return sorted(nodes)

    def descendants(self, span_id: str) -> list[str]:
        if span_id not in self._g:
            return []
        return sorted(nx.descendants(self._g, span_id))

    def parent_ids(self, span_id: str) -> list[str]:
        if span_id not in self._g:
            return []
        return sorted(self._g.predecessors(span_id))

    def explicit_ancestors(self, span_id: str) -> list[str]:
        """Ancestors reachable using only EXPLICIT edges."""
        return self._filtered_ancestors(span_id, allowed={EvidenceType.EXPLICIT})

    def inferred_path_exists(self, src_id: str, dst_id: str) -> bool:
        """True if some path from src to dst includes at least one INFERRED edge."""
        if src_id not in self._g or dst_id not in self._g:
            return False
        if not nx.has_path(self._g, src_id, dst_id):
            return False
        for path in nx.all_simple_paths(self._g, src_id, dst_id):
            inferred = False
            for a, b in zip(path, path[1:], strict=False):
                data = self._g.get_edge_data(a, b) or {}
                if data.get("evidence_type") == EvidenceType.INFERRED.value:
                    inferred = True
                    break
            if inferred:
                return True
        return False

    def lineage_status(self, span_id: str) -> ProvenanceStatus:
        """Conservative status: any inferred edge in the ancestor cone → INFERRED."""
        span = self._g.nodes.get(span_id, {}).get("span")
        if span is None:
            return ProvenanceStatus.UNKNOWN
        if span.provenance_status != ProvenanceStatus.KNOWN:
            return span.provenance_status
        for node in [span_id, *self.ancestors(span_id)]:
            for pred in self._g.predecessors(node):
                data = self._g.get_edge_data(pred, node) or {}
                if data.get("evidence_type") == EvidenceType.INFERRED.value:
                    return ProvenanceStatus.INFERRED
        return span.provenance_status

    def validate_integrity(self) -> list[str]:
        """Return a list of integrity problems (empty if OK)."""
        problems: list[str] = []
        if not nx.is_directed_acyclic_graph(self._g):
            problems.append("graph contains cycles")
        for u, v, data in self._g.edges(data=True):
            if u not in self._g.nodes or v not in self._g.nodes:
                problems.append(f"edge endpoints missing: {u} -> {v}")
            edge: ProvenanceEdge | None = data.get("edge")
            if edge and edge.evidence_type == EvidenceType.INFERRED:
                dst_span: ProvenanceSpan | None = self._g.nodes[v].get("span")
                if dst_span and dst_span.provenance_status == ProvenanceStatus.KNOWN:
                    # Destination may still be KNOWN from explicit parents; inferred edges
                    # must not be the sole justification for KNOWN. Flag if ONLY inferred parents.
                    preds = list(self._g.predecessors(v))
                    explicit_preds = [
                        p
                        for p in preds
                        if (self._g.get_edge_data(p, v) or {}).get("evidence_type")
                        == EvidenceType.EXPLICIT.value
                    ]
                    if not explicit_preds:
                        problems.append(
                            f"span {v} marked KNOWN but has only INFERRED parents"
                        )
        return problems

    def _filtered_ancestors(
        self, span_id: str, allowed: Iterable[EvidenceType]
    ) -> list[str]:
        allowed_values = {e.value for e in allowed}
        if span_id not in self._g:
            return []
        seen: set[str] = set()
        stack = list(self._g.predecessors(span_id))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            # Only walk across allowed edge types into this node from its preds later;
            # for membership, check edge from node? Wait: we pushed predecessors via edges.
            # Re-walk carefully:
            seen.add(node)
        # Correct BFS using only allowed edges (reverse direction).
        seen.clear()
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
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()
