import dagre from "@dagrejs/dagre";
import type { SpanEdge, SpanNode } from "./derive";

export const FLOW_W = 188;
export const FLOW_H = 72;

const STATUSES = new Set(["KNOWN", "INFERRED", "UNKNOWN", "PARTIAL"]);

export type FlowStatus = "KNOWN" | "INFERRED" | "UNKNOWN" | "PARTIAL" | "OTHER";

export type StoredFlowNode = {
  id: string;
  x: number;
  y: number;
  label: string;
  sublabel: string;
  status: FlowStatus;
  origin: string;
  kind: string;
  content: string;
  untrusted: boolean;
  onPath: boolean;
};

export type StoredFlowEdge = {
  id: string;
  source: string;
  target: string;
  relationship: string;
  evidence: string;
  onPath: boolean;
};

export type StoredFlow = {
  nodes: StoredFlowNode[];
  edges: StoredFlowEdge[];
};

export function flowStatus(value: string | undefined): FlowStatus {
  const status = (value || "").toUpperCase();
  return STATUSES.has(status) ? (status as FlowStatus) : "OTHER";
}

export function isUntrustedSpan(span: SpanNode | undefined): boolean {
  if (!span) return false;
  const origin = (span.origin || "").toUpperCase();
  const status = flowStatus(span.provenance_status);
  return origin.includes("UNTRUSTED") || status === "INFERRED" || status === "UNKNOWN" || status === "PARTIAL";
}

/**
 * Graph of spans and edges that already exist in the registry export.
 * Edges with a missing endpoint are dropped. No node or edge is created
 * to fill a gap.
 */
export function buildStoredFlow(
  spans: SpanNode[],
  edges: SpanEdge[],
  selectedId: string | null,
): StoredFlow {
  const byId = new Map<string, SpanNode>();
  for (const span of spans) {
    if (span.id && !byId.has(span.id)) byId.set(span.id, span);
  }
  const stored = edges.filter(
    (edge) => edge.id && byId.has(edge.source) && byId.has(edge.target),
  );
  const path = untrustedPath(byId, stored, selectedId);

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 84, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const id of byId.keys()) g.setNode(id, { width: FLOW_W, height: FLOW_H });
  for (const edge of stored) g.setEdge(edge.source, edge.target);
  dagre.layout(g);

  const nodes: StoredFlowNode[] = [...byId.values()].map((span) => {
    const placed = g.node(span.id);
    const status = flowStatus(span.provenance_status);
    return {
      id: span.id,
      x: (placed?.x ?? 0) - FLOW_W / 2,
      y: (placed?.y ?? 0) - FLOW_H / 2,
      label: span.source || span.kind || "span",
      sublabel: `${span.kind || "span"} · ${span.origin || "origin unknown"}`,
      status,
      origin: span.origin || "",
      kind: span.kind || "",
      content: span.content_redacted || "",
      untrusted: isUntrustedSpan(span),
      onPath: path.nodes.has(span.id),
    };
  });
  const flowEdges: StoredFlowEdge[] = stored.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    relationship: edge.relationship || "DERIVED_FROM",
    evidence: (edge.evidence_type || (edge.inferred ? "INFERRED" : "EXPLICIT")).toUpperCase(),
    onPath: path.edges.has(edge.id),
  }));
  return { nodes, edges: flowEdges };
}

function untrustedPath(
  byId: Map<string, SpanNode>,
  edges: SpanEdge[],
  selectedId: string | null,
): { nodes: Set<string>; edges: Set<string> } {
  const nodes = new Set<string>();
  const pathEdges = new Set<string>();
  if (!selectedId || !byId.has(selectedId)) return { nodes, edges: pathEdges };

  const incoming = new Map<string, SpanEdge[]>();
  for (const edge of edges) {
    const list = incoming.get(edge.target) || [];
    list.push(edge);
    incoming.set(edge.target, list);
  }

  const reaches = new Set<string>([selectedId]);
  const stack = [selectedId];
  while (stack.length) {
    const current = stack.pop() as string;
    for (const edge of incoming.get(current) || []) {
      if (!byId.has(edge.source) || reaches.has(edge.source)) continue;
      reaches.add(edge.source);
      stack.push(edge.source);
    }
  }

  const tainted = new Map<string, boolean>();
  const visiting = new Set<string>();
  const isTainted = (id: string): boolean => {
    const cached = tainted.get(id);
    if (cached !== undefined) return cached;
    if (visiting.has(id)) return false;
    visiting.add(id);
    let hit = isUntrustedSpan(byId.get(id));
    if (!hit) {
      for (const edge of incoming.get(id) || []) {
        if (!reaches.has(edge.source)) continue;
        const inferred =
          (edge.evidence_type || "").toUpperCase() === "INFERRED" || Boolean(edge.inferred);
        if (inferred || isTainted(edge.source)) {
          hit = true;
          break;
        }
      }
    }
    visiting.delete(id);
    tainted.set(id, hit);
    return hit;
  };

  if (isTainted(selectedId) || isUntrustedSpan(byId.get(selectedId))) nodes.add(selectedId);
  for (const edge of edges) {
    if (!reaches.has(edge.source) || !reaches.has(edge.target)) continue;
    const inferred =
      (edge.evidence_type || "").toUpperCase() === "INFERRED" || Boolean(edge.inferred);
    if (inferred || isTainted(edge.source)) {
      pathEdges.add(edge.id);
      nodes.add(edge.source);
      nodes.add(edge.target);
    }
  }
  if (pathEdges.size) nodes.add(selectedId);
  return { nodes, edges: pathEdges };
}
