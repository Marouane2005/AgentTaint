"use client";

import { useMemo, useState } from "react";

export type GraphNode = {
  id: string;
  kind?: string;
  origin?: string;
  provenance_status?: string;
  agent_id?: string | null;
  content_redacted?: string | null;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship?: string;
  evidence_type?: string;
  inferred?: boolean;
  legend?: string;
};

const STATUS_COLOR: Record<string, string> = {
  KNOWN: "#3dba8a",
  INFERRED: "#d4a017",
  UNKNOWN: "#7a8799",
  PARTIAL: "#5b8fd4",
};

function truncate(text: string | null | undefined, n = 96) {
  if (!text) return "";
  return text.length > n ? `${text.slice(0, n)}…` : text;
}

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  const layers = new Map<string, number>();
  const indeg = new Map<string, number>();
  nodes.forEach((n) => indeg.set(n.id, 0));
  edges.forEach((e) => indeg.set(e.target, (indeg.get(e.target) || 0) + 1));
  const roots = nodes.filter((n) => (indeg.get(n.id) || 0) === 0).map((n) => n.id);
  const queue = [...roots];
  queue.forEach((id) => layers.set(id, 0));
  const outgoing = new Map<string, string[]>();
  edges.forEach((e) => {
    const list = outgoing.get(e.source) || [];
    list.push(e.target);
    outgoing.set(e.source, list);
  });
  const seen = new Set<string>(queue);
  while (queue.length) {
    const id = queue.shift()!;
    const depth = layers.get(id) || 0;
    for (const nxt of outgoing.get(id) || []) {
      const nextDepth = Math.max(layers.get(nxt) || 0, depth + 1);
      layers.set(nxt, nextDepth);
      if (!seen.has(nxt)) {
        seen.add(nxt);
        queue.push(nxt);
      }
    }
  }
  nodes.forEach((n) => {
    if (!layers.has(n.id)) layers.set(n.id, 0);
  });

  const byLayer = new Map<number, GraphNode[]>();
  nodes.forEach((n) => {
    const layer = layers.get(n.id) || 0;
    const list = byLayer.get(layer) || [];
    list.push(n);
    byLayer.set(layer, list);
  });
  const positions = new Map<string, { x: number; y: number }>();
  const layerKeys = [...byLayer.keys()].sort((a, b) => a - b);
  const colW = 220;
  const rowH = 96;
  layerKeys.forEach((layer, li) => {
    const row = byLayer.get(layer) || [];
    row.forEach((n, i) => {
      positions.set(n.id, {
        x: 110 + li * colW,
        y: 70 + i * rowH,
      });
    });
  });
  const width = Math.max(760, 140 + layerKeys.length * colW);
  const height = Math.max(
    380,
    90 + Math.max(...[...byLayer.values()].map((r) => r.length), 1) * rowH,
  );
  return { positions, width, height };
}

export function ProvenanceGraph({
  nodes,
  edges,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
}) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [hover, setHover] = useState<{
    x: number;
    y: number;
    text: string;
  } | null>(null);

  const { positions, width, height } = useMemo(
    () => layout(nodes, edges),
    [nodes, edges],
  );
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);
  const relatedEdges = edges.filter(
    (e) => e.source === selectedNodeId || e.target === selectedNodeId,
  );
  const gapCount = nodes.filter(
    (n) => n.kind === "GAP" || n.provenance_status === "UNKNOWN",
  ).length;

  if (!nodes.length) {
    return (
      <div className="empty">
        No provenance spans yet. Seed a simulated demo session from Overview, or
        connect a live MCP proxy session.
      </div>
    );
  }

  return (
    <div>
      <div className="panel-meta" style={{ marginBottom: "0.65rem" }}>
        {nodes.length} nodes · {edges.length} edges · {gapCount} gaps/unknown · click
        node or edge for details
      </div>
      <div className="graph-shell" style={{ position: "relative" }}>
        <svg
          role="img"
          aria-label="Provenance graph"
          width="100%"
          viewBox={`0 0 ${width} ${height}`}
        >
          <defs>
            <marker
              id="arrow-explicit"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#8b9bb0" />
            </marker>
            <marker
              id="arrow-inferred"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#d4a017" />
            </marker>
          </defs>
          {edges.map((e) => {
            const a = positions.get(e.source);
            const b = positions.get(e.target);
            if (!a || !b) return null;
            const inferred =
              Boolean(e.inferred) || e.evidence_type === "INFERRED";
            const active = selectedEdgeId === e.id;
            const related =
              selectedNodeId &&
              (e.source === selectedNodeId || e.target === selectedNodeId);
            const muted = selectedNodeId && !related && !active;
            return (
              <g
                key={e.id}
                style={{ cursor: "pointer" }}
                opacity={muted ? 0.28 : 1}
                onClick={(ev) => {
                  ev.stopPropagation();
                  setSelectedEdgeId(e.id);
                  setSelectedNodeId(null);
                }}
                onMouseEnter={(ev) => {
                  const rect = (
                    ev.currentTarget.ownerSVGElement as SVGSVGElement
                  ).getBoundingClientRect();
                  setHover({
                    x: ev.clientX - rect.left + 12,
                    y: ev.clientY - rect.top + 12,
                    text: `${e.relationship || "EDGE"} · ${
                      inferred ? "INFERRED (not verified)" : "EXPLICIT"
                    }`,
                  });
                }}
                onMouseLeave={() => setHover(null)}
              >
                <line
                  x1={a.x + 74}
                  y1={a.y}
                  x2={b.x - 74}
                  y2={b.y}
                  stroke={inferred ? "#d4a017" : "#8b9bb0"}
                  strokeWidth={active || related ? 2.4 : inferred ? 1.8 : 1.4}
                  strokeDasharray={inferred ? "5 4" : undefined}
                  markerEnd={
                    inferred ? "url(#arrow-inferred)" : "url(#arrow-explicit)"
                  }
                />
                <text
                  x={(a.x + b.x) / 2}
                  y={(a.y + b.y) / 2 - 8}
                  textAnchor="middle"
                  fontSize="10"
                  fill={inferred ? "#d4a017" : "#6b7c90"}
                >
                  {(e.relationship || "").replace(/_/g, " ").slice(0, 22)}
                </text>
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = positions.get(n.id);
            if (!p) return null;
            const status = n.provenance_status || "UNKNOWN";
            const color = STATUS_COLOR[status] || "#7a8799";
            const active = selectedNodeId === n.id;
            const isGap = n.kind === "GAP" || status === "UNKNOWN";
            const dimmed =
              selectedNodeId &&
              selectedNodeId !== n.id &&
              !relatedEdges.some(
                (e) => e.source === n.id || e.target === n.id,
              );
            return (
              <g
                key={n.id}
                transform={`translate(${p.x - 74}, ${p.y - 30})`}
                style={{ cursor: "pointer" }}
                opacity={dimmed ? 0.3 : 1}
                onClick={() => {
                  setSelectedNodeId(n.id);
                  setSelectedEdgeId(null);
                }}
                onMouseEnter={(ev) => {
                  const svg = ev.currentTarget.ownerSVGElement as SVGSVGElement;
                  const rect = svg.getBoundingClientRect();
                  setHover({
                    x: ev.clientX - rect.left + 12,
                    y: ev.clientY - rect.top + 12,
                    text: `${n.kind || "SPAN"} · ${status} · ${
                      n.agent_id || n.origin || "—"
                    }`,
                  });
                }}
                onMouseLeave={() => setHover(null)}
              >
                <rect
                  width="148"
                  height="60"
                  rx="8"
                  fill={active ? "#1a2330" : "#121820"}
                  stroke={color}
                  strokeWidth={active ? 2.2 : 1.4}
                  strokeDasharray={isGap ? "4 3" : undefined}
                />
                <text x="10" y="18" fontSize="11" fill="#e8eef6" fontWeight="600">
                  {(n.kind || "SPAN").slice(0, 18)}
                </text>
                <text x="10" y="34" fontSize="10" fill={color} fontWeight="600">
                  {status}
                </text>
                <text x="10" y="48" fontSize="9" fill="#6b7c90">
                  {(n.agent_id || n.origin || "—").toString().slice(0, 20)}
                </text>
              </g>
            );
          })}
        </svg>
        {hover ? (
          <div
            className="graph-tooltip"
            style={{ left: hover.x, top: hover.y }}
            role="tooltip"
          >
            {hover.text}
          </div>
        ) : null}
      </div>

      <div className="panel" style={{ marginTop: "0.75rem" }}>
        <div className="panel-head">
          <h2>Selection details</h2>
        </div>
        {!selectedNode && !selectedEdge ? (
          <div className="empty" style={{ paddingTop: "0.5rem" }}>
            Select a node or edge. Dashed amber edges are INFERRED — never treat as
            verified lineage. Dashed node borders mark GAP/UNKNOWN incompleteness.
          </div>
        ) : null}
        {selectedNode ? (
          <div>
            <p style={{ margin: 0 }}>
              <span className={`pill ${selectedNode.provenance_status}`}>
                {selectedNode.provenance_status}
              </span>{" "}
              <span className="mono" style={{ color: "var(--text-muted)" }}>
                {selectedNode.id}
              </span>
            </p>
            <div className="status-grid" style={{ marginTop: "0.75rem" }}>
              <div className="status-row">
                <span className="k">Kind</span>
                <span className="v mono">{selectedNode.kind || "—"}</span>
              </div>
              <div className="status-row">
                <span className="k">Origin</span>
                <span className="v mono">{selectedNode.origin || "—"}</span>
              </div>
              <div className="status-row">
                <span className="k">Agent</span>
                <span className="v mono">{selectedNode.agent_id || "—"}</span>
              </div>
            </div>
            {selectedNode.content_redacted ? (
              <div className="detail-block">
                {truncate(String(selectedNode.content_redacted), 280)}
              </div>
            ) : null}
            <div className="legend" style={{ marginTop: "0.85rem" }}>
              {relatedEdges.map((e) => (
                <div key={e.id}>
                  <strong className="mono">{e.relationship}</strong>
                  <span>
                    {e.legend || e.evidence_type}
                    {e.inferred || e.evidence_type === "INFERRED"
                      ? " — not verified causation"
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {selectedEdge ? (
          <div>
            <p style={{ margin: 0 }}>
              <span
                className={`pill ${
                  selectedEdge.inferred || selectedEdge.evidence_type === "INFERRED"
                    ? "INFERRED"
                    : "KNOWN"
                }`}
              >
                {selectedEdge.inferred || selectedEdge.evidence_type === "INFERRED"
                  ? "INFERRED"
                  : "EXPLICIT"}
              </span>{" "}
              <span className="mono">{selectedEdge.relationship}</span>
            </p>
            <div className="status-grid" style={{ marginTop: "0.75rem" }}>
              <div className="status-row">
                <span className="k">From</span>
                <span className="v mono">{selectedEdge.source.slice(0, 12)}…</span>
              </div>
              <div className="status-row">
                <span className="k">To</span>
                <span className="v mono">{selectedEdge.target.slice(0, 12)}…</span>
              </div>
              <div className="status-row">
                <span className="k">Meaning</span>
                <span className="v">{selectedEdge.legend || "—"}</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
