"use client";

import { useMemo, useState } from "react";

type Node = {
  id: string;
  kind?: string;
  origin?: string;
  provenance_status?: string;
  agent_id?: string | null;
  content_redacted?: string | null;
};

type Edge = {
  id: string;
  source: string;
  target: string;
  relationship?: string;
  evidence_type?: string;
  inferred?: boolean;
  legend?: string;
};

const STATUS_COLOR: Record<string, string> = {
  KNOWN: "#1f7a6c",
  INFERRED: "#b07a16",
  UNKNOWN: "#6b7280",
  PARTIAL: "#3b6ea5",
};

function layout(nodes: Node[], edges: Edge[]) {
  const layers = new Map<string, number>();
  const indeg = new Map<string, number>();
  nodes.forEach((n) => indeg.set(n.id, 0));
  edges.forEach((e) => indeg.set(e.target, (indeg.get(e.target) || 0) + 1));
  const queue = nodes.filter((n) => (indeg.get(n.id) || 0) === 0).map((n) => n.id);
  queue.forEach((id) => layers.set(id, 0));
  const outgoing = new Map<string, string[]>();
  edges.forEach((e) => {
    const list = outgoing.get(e.source) || [];
    list.push(e.target);
    outgoing.set(e.source, list);
  });
  while (queue.length) {
    const id = queue.shift()!;
    const depth = layers.get(id) || 0;
    for (const nxt of outgoing.get(id) || []) {
      const nextDepth = Math.max(layers.get(nxt) || 0, depth + 1);
      layers.set(nxt, nextDepth);
      queue.push(nxt);
    }
  }
  const byLayer = new Map<number, Node[]>();
  nodes.forEach((n) => {
    const layer = layers.get(n.id) || 0;
    const list = byLayer.get(layer) || [];
    list.push(n);
    byLayer.set(layer, list);
  });
  const positions = new Map<string, { x: number; y: number }>();
  const layerKeys = [...byLayer.keys()].sort((a, b) => a - b);
  layerKeys.forEach((layer, li) => {
    const row = byLayer.get(layer) || [];
    row.forEach((n, i) => {
      positions.set(n.id, {
        x: 120 + li * 210,
        y: 70 + i * 90,
      });
    });
  });
  const width = Math.max(720, 120 + layerKeys.length * 210);
  const height = Math.max(
    360,
    80 + Math.max(...[...byLayer.values()].map((r) => r.length), 1) * 90,
  );
  return { positions, width, height };
}

export function ProvenanceGraph({
  nodes,
  edges,
}: {
  nodes: Node[];
  edges: Edge[];
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const { positions, width, height } = useMemo(
    () => layout(nodes, edges),
    [nodes, edges],
  );
  const selectedNode = nodes.find((n) => n.id === selected);
  const selectedEdges = edges.filter(
    (e) => e.source === selected || e.target === selected,
  );

  if (!nodes.length) {
    return <div className="empty">No provenance spans yet. Seed the demo session.</div>;
  }

  return (
    <div>
      <svg
        role="img"
        aria-label="Provenance graph"
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        style={{ background: "#fff", borderRadius: 8, border: "1px solid var(--line)" }}
      >
        {edges.map((e) => {
          const a = positions.get(e.source);
          const b = positions.get(e.target);
          if (!a || !b) return null;
          const inferred = Boolean(e.inferred) || e.evidence_type === "INFERRED";
          return (
            <g key={e.id}>
              <line
                x1={a.x + 70}
                y1={a.y}
                x2={b.x - 70}
                y2={b.y}
                stroke={inferred ? "#b07a16" : "#5b6b76"}
                strokeWidth={inferred ? 2 : 1.5}
                strokeDasharray={inferred ? "6 4" : undefined}
                markerEnd="url(#arrow)"
              />
              <text
                x={(a.x + b.x) / 2}
                y={(a.y + b.y) / 2 - 6}
                textAnchor="middle"
                fontSize="10"
                fill="#5b6b76"
              >
                {e.relationship}
              </text>
            </g>
          );
        })}
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#5b6b76" />
          </marker>
        </defs>
        {nodes.map((n) => {
          const p = positions.get(n.id);
          if (!p) return null;
          const color = STATUS_COLOR[n.provenance_status || "UNKNOWN"] || "#6b7280";
          const active = selected === n.id;
          return (
            <g
              key={n.id}
              transform={`translate(${p.x - 70}, ${p.y - 28})`}
              style={{ cursor: "pointer" }}
              onClick={() => setSelected(n.id)}
            >
              <rect
                width="140"
                height="56"
                rx="8"
                fill={active ? "#f0faf7" : "#fff"}
                stroke={color}
                strokeWidth={active ? 2.5 : 1.5}
              />
              <text x="10" y="18" fontSize="11" fill="#13212b" fontWeight="600">
                {(n.kind || "SPAN").slice(0, 16)}
              </text>
              <text x="10" y="34" fontSize="10" fill={color}>
                {n.provenance_status}
              </text>
              <text x="10" y="48" fontSize="9" fill="#5b6b76">
                {(n.agent_id || n.origin || "").toString().slice(0, 18)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="panel" style={{ marginTop: "0.75rem" }}>
        <h2>Selection</h2>
        {!selectedNode ? (
          <div className="empty">Click a node to inspect status, origin, and edges.</div>
        ) : (
          <div>
            <p>
              <span className={`pill ${selectedNode.provenance_status}`}>
                {selectedNode.provenance_status}
              </span>{" "}
              <span className="mono">{selectedNode.id.slice(0, 8)}…</span>
            </p>
            <p style={{ color: "var(--muted)" }}>
              kind={selectedNode.kind} · origin={selectedNode.origin} · agent=
              {selectedNode.agent_id || "—"}
            </p>
            {selectedNode.content_redacted ? (
              <p className="mono" style={{ fontSize: "0.85rem" }}>
                {selectedNode.content_redacted}
              </p>
            ) : null}
            <div className="legend" style={{ marginTop: "0.75rem" }}>
              {selectedEdges.map((e) => (
                <div key={e.id}>
                  <strong className="mono">{e.relationship}</strong>
                  <span>
                    {e.legend || e.evidence_type}
                    {e.inferred ? " (dashed = INFERRED, not verified)" : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
