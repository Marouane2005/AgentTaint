/**
 * Pure transforms from real API payloads (audit decisions, provenance graph,
 * seeded traces) into dashboard view models. Nothing here invents data.
 */
import type { Decision, Trace } from "./api";

export type SpanNode = {
  id: string;
  kind?: string;
  origin?: string;
  provenance_status?: string;
  agent_id?: string | null;
  source?: string | null;
  content_redacted?: string | null;
  created_at?: string;
  parent_ids?: string[];
};

export type SpanEdge = {
  id: string;
  source: string;
  target: string;
  relationship?: string;
  evidence_type?: string;
  inferred?: boolean;
};

export type NodeCategory = "source" | "agent" | "transform" | "output" | "action";

export type ViewNode = {
  id: string;
  category: NodeCategory;
  label: string;
  sublabel: string;
  status?: string;
  decision?: string;
  span?: SpanNode;
  call?: Decision;
};

export type ViewEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  kind: "explicit" | "inferred" | "evaluated" | "executed";
};

export const DECISIONS = ["ALLOW", "CONFIRM", "BLOCK"] as const;

/** Parse an API timestamp; naive ISO strings from the audit store are UTC. */
export function parseTs(value: string | undefined | null): number {
  if (!value) return NaN;
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(value);
  return Date.parse(hasZone ? value : `${value}Z`);
}

export function formatUtcTime(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  const d = new Date(ms);
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.${pad(
    d.getUTCMilliseconds(),
    3,
  )}`;
}

export function countBy<T>(items: T[], key: (t: T) => string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const item of items) {
    const k = key(item);
    out[k] = (out[k] || 0) + 1;
  }
  return out;
}

export type TimelineBin = {
  start: number;
  end: number;
  ALLOW: number;
  CONFIRM: number;
  BLOCK: number;
};

/** Bin decisions over their real time range into ``bins`` equal buckets. */
export function decisionTimeline(decisions: Decision[], bins = 24): {
  bins: TimelineBin[];
  widthMs: number;
} {
  const times = decisions.map((d) => parseTs(d.created_at)).filter(Number.isFinite);
  if (!times.length) return { bins: [], widthMs: 0 };
  const min = Math.min(...times);
  const max = Math.max(...times);
  const widthMs = Math.max(1, Math.ceil((max - min + 1) / bins));
  const out: TimelineBin[] = Array.from({ length: bins }, (_, i) => ({
    start: min + i * widthMs,
    end: min + (i + 1) * widthMs,
    ALLOW: 0,
    CONFIRM: 0,
    BLOCK: 0,
  }));
  for (const d of decisions) {
    const t = parseTs(d.created_at);
    if (!Number.isFinite(t)) continue;
    const idx = Math.min(bins - 1, Math.floor((t - min) / widthMs));
    if (d.decision === "ALLOW" || d.decision === "CONFIRM" || d.decision === "BLOCK") {
      out[idx][d.decision] += 1;
    }
  }
  return { bins: out, widthMs };
}

export type Gauges = {
  blockRate: number;
  reviewLoad: number;
  unverifiedProvenance: number;
  inferredLineage: number;
};

export function riskGauges(decisions: Decision[], edges: SpanEdge[]): Gauges {
  const total = decisions.length;
  const frac = (n: number, d: number) => (d ? n / d : 0);
  return {
    blockRate: frac(decisions.filter((d) => d.decision === "BLOCK").length, total),
    reviewLoad: frac(decisions.filter((d) => d.decision === "CONFIRM").length, total),
    unverifiedProvenance: frac(
      decisions.filter((d) => (d.provenance_status || "UNKNOWN") !== "KNOWN").length,
      total,
    ),
    inferredLineage: frac(
      edges.filter((e) => e.inferred || e.evidence_type === "INFERRED").length,
      edges.length,
    ),
  };
}

/** Destination class from a redacted argument map (raw addresses are never stored). */
export function destinationClass(args: Record<string, unknown> | undefined): string {
  const text = JSON.stringify(args || {});
  if (text.includes("[REDACTED_EMAIL]")) return "Email recipient";
  if (text.includes("[REDACTED_URL]")) return "Web endpoint";
  if (text.includes("[REDACTED_IP]")) return "IP address";
  if (/"(path|file|filename)"/.test(text)) return "Filesystem";
  if (/"(iban|amount|account)"/.test(text)) return "Payment";
  return "No external destination";
}

export type FlowLink = {
  from: string;
  to: string;
  decision: string;
  count: number;
};

export function destinationFlows(decisions: Decision[]): {
  agents: string[];
  tools: string[];
  destinations: string[];
  links: FlowLink[];
} {
  const agents = new Set<string>();
  const tools = new Set<string>();
  const destinations = new Set<string>();
  const map = new Map<string, FlowLink>();
  const add = (from: string, to: string, decision: string) => {
    const key = `${from}\u0000${to}\u0000${decision}`;
    const link = map.get(key) || { from, to, decision, count: 0 };
    link.count += 1;
    map.set(key, link);
  };
  for (const d of decisions) {
    const agent = `agent:${d.agent_id || "unknown"}`;
    const tool = `tool:${d.tool}`;
    const dest = `dest:${destinationClass(d.arguments_redacted)}`;
    agents.add(agent);
    tools.add(tool);
    destinations.add(dest);
    add(agent, tool, d.decision);
    add(tool, dest, d.decision);
  }
  return {
    agents: [...agents].sort(),
    tools: [...tools].sort(),
    destinations: [...destinations].sort(),
    links: [...map.values()],
  };
}

function shortText(text: string | null | undefined, n = 42): string {
  if (!text) return "";
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

const TRANSFORM_KINDS = new Set(["SUMMARY", "EXTRACT", "REWRITE", "MEMORY", "GAP"]);

/**
 * Build the trace DAG: provenance spans plus one "action" node per gateway
 * decision. Argument spans created during a call feed the action; results of
 * the called tool are what the action executed.
 */
export function buildTraceGraph(
  spans: SpanNode[],
  edges: SpanEdge[],
  decisions: Decision[],
  trace: Trace | null,
): { nodes: ViewNode[]; edges: ViewEdge[] } {
  const spanIds = trace ? new Set(trace.span_ids) : new Set(spans.map((s) => s.id));
  const callIds = trace ? new Set(trace.call_ids) : new Set(decisions.map((d) => d.call_id));
  const inSpans = spans.filter((s) => spanIds.has(s.id));
  const inCalls = decisions.filter((d) => callIds.has(d.call_id));
  const groups: { call_ids: string[]; span_ids: string[] }[] = trace?.calls?.length
    ? trace.calls
    : trace
      ? [{ call_ids: trace.call_ids, span_ids: trace.span_ids }]
      : [];

  const executedResult = new Set<string>();
  const viewEdges: ViewEdge[] = [];
  const byId = new Map(inSpans.map((s) => [s.id, s]));
  for (const g of groups) {
    for (const cid of g.call_ids) {
      const call = inCalls.find((d) => d.call_id === cid);
      if (!call) continue;
      for (const sid of g.span_ids) {
        const span = byId.get(sid);
        if (!span) continue;
        if (span.kind === "TOOL_ARG") {
          viewEdges.push({
            id: `eval:${sid}:${cid}`,
            source: sid,
            target: `call:${cid}`,
            label: "EVALUATED",
            kind: "evaluated",
          });
        } else if (span.kind === "TOOL_RESULT" && span.source === call.tool) {
          executedResult.add(sid);
          viewEdges.push({
            id: `exec:${cid}:${sid}`,
            source: `call:${cid}`,
            target: sid,
            label: "EXECUTED",
            kind: "executed",
          });
        }
      }
    }
  }

  const hasDownstream = new Set(
    edges.filter((e) => spanIds.has(e.source) && spanIds.has(e.target)).map((e) => e.source),
  );
  const nodes: ViewNode[] = inSpans.map((s) => {
    let category: NodeCategory;
    if (s.kind === "AGENT_MESSAGE") category = "agent";
    else if (s.kind && TRANSFORM_KINDS.has(s.kind)) category = "transform";
    else if (s.kind === "TOOL_ARG") category = "output";
    else if (executedResult.has(s.id) && !hasDownstream.has(s.id)) category = "output";
    else category = "source";
    const head =
      category === "agent" ? (s.agent_id || "agent") : s.source && s.source !== "transformation"
        ? s.source
        : (s.kind || "span").toLowerCase();
    return {
      id: s.id,
      category,
      label: head,
      sublabel: `${s.kind || "?"} · ${s.origin || "?"}`,
      status: s.provenance_status,
      span: s,
    };
  });
  for (const d of inCalls) {
    nodes.push({
      id: `call:${d.call_id}`,
      category: "action",
      label: d.tool,
      sublabel: `${d.decision} · ${d.risk_tier}`,
      decision: d.decision,
      status: d.provenance_status,
      call: d,
    });
  }
  for (const e of edges) {
    if (!spanIds.has(e.source) || !spanIds.has(e.target)) continue;
    const inferred = Boolean(e.inferred || e.evidence_type === "INFERRED");
    viewEdges.push({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.relationship || "DERIVED_FROM",
      kind: inferred ? "inferred" : "explicit",
    });
  }
  return { nodes, edges: viewEdges };
}

/** For each source node, count the decisions it reaches, by outcome. */
export function flowsBySource(
  nodes: ViewNode[],
  edges: ViewEdge[],
): Array<{ node: ViewNode; counts: Record<string, number> }> {
  const out = new Map<string, string[]>();
  for (const e of edges) {
    const list = out.get(e.source) || [];
    list.push(e.target);
    out.set(e.source, list);
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return nodes
    .filter((n) => n.category === "source")
    .map((node) => {
      const seen = new Set<string>([node.id]);
      const stack = [node.id];
      const counts: Record<string, number> = {};
      while (stack.length) {
        const id = stack.pop()!;
        for (const nxt of out.get(id) || []) {
          if (seen.has(nxt)) continue;
          seen.add(nxt);
          stack.push(nxt);
          const n = byId.get(nxt);
          if (n?.category === "action" && n.decision) {
            counts[n.decision] = (counts[n.decision] || 0) + 1;
          }
        }
      }
      return { node, counts };
    });
}

export type TimelineEvent = {
  at: number;
  type: string;
  detail: string;
  tone: "allow" | "block" | "confirm" | "info" | "warn";
};

export function toolUsage(decisions: Decision[]): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const decision of decisions) {
    const name = decision.tool || "unknown";
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function provenanceCoverage(nodes: SpanNode[]): {
  total: number;
  known: number;
  inferred: number;
  unknown: number;
  partial: number;
  other: number;
} {
  const counts = { total: nodes.length, known: 0, inferred: 0, unknown: 0, partial: 0, other: 0 };
  for (const node of nodes) {
    const status = (node.provenance_status || "").toUpperCase();
    if (status === "KNOWN") counts.known += 1;
    else if (status === "INFERRED") counts.inferred += 1;
    else if (status === "UNKNOWN") counts.unknown += 1;
    else if (status === "PARTIAL") counts.partial += 1;
    else counts.other += 1;
  }
  return counts;
}

export function traceTimeline(nodes: ViewNode[]): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  for (const n of nodes) {
    if (n.call) {
      const d = n.call;
      events.push({
        at: parseTs(d.created_at),
        type: `${d.decision} ${d.tool}`,
        detail: `${d.policy_id || "—"} · ${d.risk_tier} · ${d.agent_id || "—"}`,
        tone: d.decision === "ALLOW" ? "allow" : d.decision === "BLOCK" ? "block" : "confirm",
      });
    } else if (n.span) {
      const s = n.span;
      events.push({
        at: parseTs(s.created_at),
        type: s.kind || "SPAN",
        detail: `${s.origin || "?"} · ${shortText(s.content_redacted, 64) || s.source || ""}`,
        tone:
          s.origin === "UNTRUSTED_TOOL" ? "warn" : s.provenance_status === "INFERRED" ? "confirm" : "info",
      });
    }
  }
  return events.sort((a, b) => (a.at || 0) - (b.at || 0));
}
