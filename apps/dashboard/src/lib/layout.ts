import dagre from "@dagrejs/dagre";
import type { NodeCategory, ViewEdge, ViewNode } from "./derive";

export const NODE_W = 150;
export const NODE_H = 54;

export type Placed = { x: number; y: number };
export type EdgePath = { id: string; points: Placed[]; labelAt: Placed };
export type Column = { x: number; label: string };

const COLUMN_LABEL: Record<NodeCategory, string> = {
  source: "Sources",
  agent: "Agents",
  transform: "Tools & memory",
  output: "Outputs & sinks",
  action: "Final action",
};

/** Left-to-right layered layout (dagre) with labelled rank columns. */
export function layoutDag(nodes: ViewNode[], edges: ViewEdge[]) {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setGraph({ rankdir: "LR", nodesep: 26, ranksep: 120, marginx: 40, marginy: 70 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target, { width: 60, height: 14, labelpos: "c" }, e.id);
    }
  }
  dagre.layout(g);
  const positions = new Map<string, Placed>();
  for (const n of nodes) {
    const p = g.node(n.id);
    if (p) positions.set(n.id, { x: p.x, y: p.y });
  }
  // Disconnected nodes (e.g. a decision on a call with no recorded lineage) go to
  // a column right of the graph so they never pose as sources.
  const connected = new Set(edges.flatMap((e) => [e.source, e.target]));
  const isolated = nodes.filter((n) => !connected.has(n.id));
  if (isolated.length && isolated.length < nodes.length) {
    const xs = [...positions.values()].map((p) => p.x);
    const maxX = Math.max(...xs);
    const right = isolated.every((n) => n.category === "action") ? maxX : maxX + NODE_W + 60;
    const used = nodes
      .filter((n) => connected.has(n.id))
      .map((n) => positions.get(n.id)!)
      .filter((p) => Math.abs(p.x - right) < 1)
      .map((p) => p.y);
    let y = (used.length ? Math.max(...used) : 40) + NODE_H + 30;
    for (const n of isolated) {
      positions.set(n.id, { x: right, y });
      y += NODE_H + 26;
    }
  }
  const paths: EdgePath[] = [];
  for (const e of edges) {
    if (!g.hasEdge(e.source, e.target, e.id)) continue;
    const ge = g.edge(e.source, e.target, e.id) as unknown as {
      points: Placed[];
      x?: number;
      y?: number;
    };
    const pts = ge.points || [];
    const mid = pts[Math.floor(pts.length / 2)] || { x: 0, y: 0 };
    paths.push({ id: e.id, points: pts, labelAt: { x: ge.x ?? mid.x, y: ge.y ?? mid.y } });
  }
  // Column labels: cluster x positions, label by dominant category.
  const cols = new Map<number, Map<NodeCategory, number>>();
  for (const n of nodes) {
    const p = positions.get(n.id);
    if (!p) continue;
    const key = Math.round(p.x);
    const m = cols.get(key) || new Map<NodeCategory, number>();
    m.set(n.category, (m.get(n.category) || 0) + 1);
    cols.set(key, m);
  }
  const columns: Column[] = [...cols.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([x, m]) => {
      const ranked = [...m.entries()].sort((a, b) => b[1] - a[1]);
      const label = ranked
        .slice(0, 2)
        .filter(([, n], i) => i === 0 || n === ranked[0][1])
        .map(([c]) => COLUMN_LABEL[c])
        .join(" · ");
      return { x, label };
    });
  const graph = g.graph();
  const all = [...positions.values()];
  const maxX = all.length ? Math.max(...all.map((p) => p.x)) + NODE_W / 2 + 40 : 0;
  const maxY = all.length ? Math.max(...all.map((p) => p.y)) + NODE_H / 2 + 40 : 0;
  return {
    positions,
    paths,
    columns,
    width: Math.max(600, graph.width || 600, maxX),
    height: Math.max(360, graph.height || 360, maxY),
  };
}

/** Smooth cubic path through dagre's control points. */
export function curvePath(points: Placed[]): string {
  if (!points.length) return "";
  if (points.length < 3) {
    const [a, b = a] = points;
    const dx = (b.x - a.x) / 2;
    return `M${a.x},${a.y} C${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x},${b.y}`;
  }
  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const p = points[i];
    const n = points[i + 1];
    const mx = (p.x + n.x) / 2;
    const my = (p.y + n.y) / 2;
    d += ` Q${p.x},${p.y} ${mx},${my}`;
  }
  const last = points[points.length - 1];
  d += ` L${last.x},${last.y}`;
  return d;
}
