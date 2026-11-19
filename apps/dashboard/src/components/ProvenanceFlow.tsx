"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type EdgeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { SpanEdge, SpanNode } from "@/lib/derive";
import { buildStoredFlow, type StoredFlowEdge, type StoredFlowNode } from "@/lib/flowGraph";

type SpanData = StoredFlowNode & { selected: boolean };

function SpanView({ data }: { data: SpanData }) {
  return (
    <div
      className={[
        "span-node",
        `status-${data.status}`,
        data.onPath ? "on-path" : "",
        data.untrusted ? "untrusted" : "",
        data.selected ? "is-selected" : "",
      ].join(" ")}
    >
      <span className="span-kicker">{data.status}</span>
      <strong>{data.label}</strong>
      <span className="span-sub">{data.sublabel}</span>
    </div>
  );
}

const nodeTypes = { span: SpanView };

function FlowCanvas({
  spans,
  edges,
  selectedId,
  onSelect,
  revealKey,
}: {
  spans: SpanNode[];
  edges: SpanEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  revealKey: string;
}) {
  const model = useMemo(
    () => buildStoredFlow(spans, edges, selectedId),
    [spans, edges, selectedId],
  );
  const [edgeId, setEdgeId] = useState<string | null>(null);
  const [reveal, setReveal] = useState(true);

  useEffect(() => {
    setReveal(true);
    setEdgeId(null);
    const reduce =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const timer = window.setTimeout(() => setReveal(false), 700);
    return () => window.clearTimeout(timer);
  }, [revealKey]);

  const reduceMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nodes: Node<SpanData>[] = model.nodes.map((node) => ({
    id: node.id,
    type: "span",
    position: { x: node.x, y: node.y },
    data: { ...node, selected: node.id === selectedId },
    selected: node.id === selectedId,
  }));
  const flowEdges: Edge[] = model.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.relationship,
    animated: !reduceMotion && edge.onPath && edge.evidence === "INFERRED",
    style: {
      stroke: edge.onPath ? "#f05252" : edge.evidence === "INFERRED" ? "#f5b942" : "#22d3ee",
      strokeWidth: edge.id === edgeId || edge.onPath ? 2.4 : 1.4,
    },
    labelStyle: { fill: "#c5d4e8", fontSize: 10 },
    labelBgStyle: { fill: "#0c1220" },
    data: edge,
  }));
  const activeEdge = model.edges.find((edge) => edge.id === edgeId) || null;

  const onNodeClick: NodeMouseHandler<Node<SpanData>> = (_, node) => {
    onSelect(node.id);
    setEdgeId(null);
  };
  const onEdgeClick: EdgeMouseHandler = (_, edge) => {
    setEdgeId(edge.id);
  };

  if (!nodes.length) {
    return <div className="empty">No stored spans for this trace.</div>;
  }

  return (
    <div className={reveal ? "flow-shell reveal" : "flow-shell"}>
      <div className="flow-canvas" role="img" aria-label="Provenance graph of stored spans and edges">
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={() => {
            onSelect(null);
            setEdgeId(null);
          }}
          fitView
          fitViewOptions={{ duration: reduceMotion ? 0 : 450 }}
          minZoom={0.35}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
        >
          <Background color="#1a2744" gap={18} />
          <Controls showInteractive={false} />
        </ReactFlow>
        <ul className="flow-legend" aria-label="Provenance status">
          {(["KNOWN", "INFERRED", "UNKNOWN", "PARTIAL"] as const).map((status) => (
            <li key={status}>
              <i className={`swatch status-${status}`} />
              {status}
            </li>
          ))}
          <li>
            <i className="swatch path" />
            Untrusted path
          </li>
        </ul>
      </div>
      <p className="fine">Stored registry edges only. A gap is left blank.</p>
      {activeEdge ? <EdgeCard edge={activeEdge} onClose={() => setEdgeId(null)} /> : null}
    </div>
  );
}

function EdgeCard({ edge, onClose }: { edge: StoredFlowEdge; onClose: () => void }) {
  return (
    <aside className="edge-card" aria-label="Edge inspection">
      <header>
        <strong>{edge.relationship}</strong>
        <button type="button" onClick={onClose} aria-label="Close edge">
          ×
        </button>
      </header>
      <dl>
        <dt>Evidence</dt>
        <dd>{edge.evidence}</dd>
        <dt>From</dt>
        <dd className="mono">{edge.source}</dd>
        <dt>To</dt>
        <dd className="mono">{edge.target}</dd>
        <dt>Path</dt>
        <dd>{edge.onPath ? "On the untrusted path to the selection" : "Stored, not on that path"}</dd>
      </dl>
    </aside>
  );
}

export function ProvenanceFlow(props: {
  spans: SpanNode[];
  edges: SpanEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  revealKey?: string;
}) {
  return (
    <ReactFlowProvider>
      <FlowCanvas {...props} revealKey={props.revealKey || "trace"} />
    </ReactFlowProvider>
  );
}
