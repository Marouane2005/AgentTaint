"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import { flowsBySource, type ViewEdge, type ViewNode } from "@/lib/derive";
import { curvePath, layoutDag, NODE_H, NODE_W } from "@/lib/layout";

const EDGE_STYLE: Record<ViewEdge["kind"], { stroke: string; dash?: string }> = {
  explicit: { stroke: "#4f8cff" },
  inferred: { stroke: "#e0a526", dash: "6 5" },
  evaluated: { stroke: "#38c6f4" },
  executed: { stroke: "#7aa2ff", dash: "2 4" },
};

const DECISION_COLOR: Record<string, string> = {
  ALLOW: "#2fd39a",
  CONFIRM: "#f2b937",
  BLOCK: "#ff5f6d",
};

function NodeShape({ node, selected }: { node: ViewNode; selected: boolean }) {
  const w = NODE_W;
  const h = NODE_H;
  const ring = selected ? "#ffffff" : "transparent";
  const dashed = node.status === "UNKNOWN" || node.span?.kind === "GAP";
  const iconX = -w / 2 + 22;
  let icon: React.ReactNode;
  switch (node.category) {
    case "source":
      icon = (
        <polygon
          points={`${iconX},-14 ${iconX + 14},0 ${iconX},14 ${iconX - 14},0`}
          fill="#8a93a3"
          stroke={ring}
          strokeWidth={2}
        />
      );
      break;
    case "agent":
      icon = <circle cx={iconX} cy={0} r={13} fill="#2fd39a" stroke={ring} strokeWidth={2} />;
      break;
    case "transform":
      icon = (
        <rect
          x={iconX - 12}
          y={-12}
          width={24}
          height={24}
          rx={6}
          fill="#e04fd0"
          stroke={ring}
          strokeWidth={2}
        />
      );
      break;
    case "output":
      icon = (
        <rect
          x={iconX - 12}
          y={-12}
          width={24}
          height={24}
          rx={3}
          fill="#f5d142"
          stroke={ring}
          strokeWidth={2}
        />
      );
      break;
    default:
      icon = (
        <g>
          <rect
            x={iconX - 13}
            y={-13}
            width={26}
            height={26}
            rx={13}
            fill="#3b7bff"
            stroke={ring}
            strokeWidth={2}
          />
          <circle cx={iconX} cy={0} r={5} fill={DECISION_COLOR[node.decision || ""] || "#fff"} />
        </g>
      );
  }
  return (
    <g>
      <rect
        x={-w / 2}
        y={-h / 2}
        width={w}
        height={h}
        rx={10}
        className={`tg-card ${node.category}${selected ? " selected" : ""}`}
        strokeDasharray={dashed ? "4 3" : undefined}
      />
      {icon}
      <text x={iconX + 22} y={-4} className="tg-label">
        {node.label.length > 15 ? `${node.label.slice(0, 14)}…` : node.label}
      </text>
      <text x={iconX + 22} y={12} className="tg-sublabel">
        {node.sublabel.length > 20 ? `${node.sublabel.slice(0, 19)}…` : node.sublabel}
      </text>
      {node.decision ? (
        <text
          x={w / 2 - 8}
          y={-h / 2 + 13}
          textAnchor="end"
          className="tg-badge"
          fill={DECISION_COLOR[node.decision] || "#fff"}
        >
          {node.decision}
        </text>
      ) : null}
    </g>
  );
}

export function TraceGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: ViewNode[];
  edges: ViewEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const layout = useMemo(() => layoutDag(nodes, edges), [nodes, edges]);
  const flows = useMemo(() => flowsBySource(nodes, edges), [nodes, edges]);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  const [showFlows, setShowFlows] = useState(true);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const fit = useCallback(() => {
    const el = wrapRef.current;
    const w = el?.clientWidth || 900;
    const h = el?.clientHeight || 560;
    const k = Math.min(1.4, Math.max(0.2, Math.min(w / layout.width, h / layout.height)));
    setView({ k, x: (w - layout.width * k) / 2, y: (h - layout.height * k) / 2 });
  }, [layout.width, layout.height]);

  useEffect(() => {
    fit();
  }, [fit]);

  const zoomBy = (factor: number) =>
    setView((v) => {
      const el = wrapRef.current;
      const cx = (el?.clientWidth || 900) / 2;
      const cy = (el?.clientHeight || 560) / 2;
      const k = Math.min(3, Math.max(0.15, v.k * factor));
      return { k, x: cx - ((cx - v.x) * k) / v.k, y: cy - ((cy - v.y) * k) / v.k };
    });

  function onWheel(e: ReactWheelEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    setView((v) => {
      const k = Math.min(3, Math.max(0.15, v.k * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
      return { k, x: px - ((px - v.x) * k) / v.k, y: py - ((py - v.y) * k) / v.k };
    });
  }

  function onPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    if ((e.target as Element).closest("[data-node]")) return;
    drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    const d = drag.current;
    if (!d) return;
    setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
  }
  function onPointerUp() {
    drag.current = null;
  }

  const edgeById = new Map(edges.map((e) => [e.id, e]));

  return (
    <div className="tg-wrap">
      <div
        ref={wrapRef}
        className="tg-canvas"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        role="img"
        aria-label="Provenance trace graph"
      >
        {!nodes.length ? (
          <div className="tg-empty">No spans for this trace. Seed the demo session first.</div>
        ) : null}
        <svg width="100%" height="100%">
          <defs>
            {Object.entries(EDGE_STYLE).map(([k, s]) => (
              <marker
                key={k}
                id={`arrow-${k}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L10,5 L0,10 z" fill={s.stroke} />
              </marker>
            ))}
          </defs>
          <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
            {layout.columns.map((c, i) => (
              <g key={`${c.x}-${i}`}>
                <line
                  x1={c.x}
                  x2={c.x}
                  y1={28}
                  y2={layout.height - 10}
                  className="tg-col-line"
                />
                <text x={c.x} y={22} textAnchor="middle" className="tg-col-label">
                  {c.label.toUpperCase()}
                </text>
              </g>
            ))}
            {layout.paths.map((p) => {
              const e = edgeById.get(p.id);
              if (!e) return null;
              const s = EDGE_STYLE[e.kind];
              return (
                <g key={p.id} className="tg-edge">
                  <path
                    d={curvePath(p.points)}
                    fill="none"
                    stroke={s.stroke}
                    strokeWidth={1.6}
                    strokeDasharray={s.dash}
                    markerEnd={`url(#arrow-${e.kind})`}
                    opacity={0.9}
                  />
                  <text x={p.labelAt.x} y={p.labelAt.y - 4} className="tg-edge-label">
                    {e.label}
                  </text>
                </g>
              );
            })}
            {nodes.map((n) => {
              const pos = layout.positions.get(n.id);
              if (!pos) return null;
              return (
                <g
                  key={n.id}
                  data-node={n.id}
                  transform={`translate(${pos.x},${pos.y})`}
                  onClick={() => onSelect(selectedId === n.id ? null : n.id)}
                  style={{ cursor: "pointer" }}
                  role="button"
                  aria-label={`${n.category} ${n.label}`}
                >
                  <NodeShape node={n} selected={selectedId === n.id} />
                </g>
              );
            })}
          </g>
        </svg>

        <div className="tg-zoom" onPointerDown={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => zoomBy(1.2)} aria-label="Zoom in">
            +
          </button>
          <button type="button" onClick={() => zoomBy(1 / 1.2)} aria-label="Zoom out">
            −
          </button>
          <button type="button" onClick={fit} aria-label="Fit graph">
            ⤢
          </button>
          <span className="tg-zoom-k mono">{Math.round(view.k * 100)}%</span>
        </div>

        {flows.length ? (
          <div className="tg-popover" onPointerDown={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="tg-popover-head"
              onClick={() => setShowFlows((v) => !v)}
            >
              Flows by source <span>{showFlows ? "▾" : "▸"}</span>
            </button>
            {showFlows ? (
              <ul>
                {flows.slice(0, 8).map(({ node, counts }) => (
                  <li key={node.id}>
                    <span className="tg-src-dot" />
                    <span className="tg-src-name" title={node.sublabel}>
                      {node.label}
                      <small>{node.span?.origin || ""}</small>
                    </span>
                    <span className="tg-badges">
                      {Object.keys(counts).length ? (
                        Object.entries(counts).map(([d, c]) => (
                          <span key={d} className={`tg-chip ${d}`}>
                            {d} {c}
                          </span>
                        ))
                      ) : (
                        <span className="tg-chip none">no action</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="tg-legend" onPointerDown={(e) => e.stopPropagation()}>
          <div className="tg-legend-title">Node types</div>
          <div className="tg-legend-row">
            <svg width="14" height="14">
              <polygon points="7,0 14,7 7,14 0,7" fill="#8a93a3" />
            </svg>
            Source / input
          </div>
          <div className="tg-legend-row">
            <svg width="14" height="14">
              <circle cx="7" cy="7" r="6" fill="#2fd39a" />
            </svg>
            Agent
          </div>
          <div className="tg-legend-row">
            <svg width="14" height="14">
              <rect width="14" height="14" rx="4" fill="#e04fd0" />
            </svg>
            Tool step / memory
          </div>
          <div className="tg-legend-row">
            <svg width="14" height="14">
              <rect width="14" height="14" rx="2" fill="#f5d142" />
            </svg>
            Output / sink
          </div>
          <div className="tg-legend-row">
            <svg width="14" height="14">
              <rect width="14" height="14" rx="7" fill="#3b7bff" />
            </svg>
            Final action (gateway decision)
          </div>
          <div className="tg-legend-title">Edges</div>
          {(
            [
              ["explicit", "Explicit lineage"],
              ["inferred", "Inferred (not verified causation)"],
              ["evaluated", "Argument evaluated"],
              ["executed", "Tool executed"],
            ] as const
          ).map(([k, label]) => (
            <div className="tg-legend-row" key={k}>
              <svg width="22" height="8">
                <line
                  x1="0"
                  y1="4"
                  x2="22"
                  y2="4"
                  stroke={EDGE_STYLE[k].stroke}
                  strokeWidth="2"
                  strokeDasharray={EDGE_STYLE[k].dash}
                />
              </svg>
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
