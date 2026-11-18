import { describe, expect, it } from "vitest";
import type { Decision, Trace } from "./api";
import {
  buildTraceGraph,
  decisionTimeline,
  destinationClass,
  destinationFlows,
  flowsBySource,
  parseTs,
  riskGauges,
  traceTimeline,
  type SpanEdge,
  type SpanNode,
} from "./derive";
import { curvePath, layoutDag } from "./layout";

const spans: SpanNode[] = [
  { id: "s1", kind: "TOOL_RESULT", origin: "UNTRUSTED_TOOL", source: "email.read", created_at: "2026-11-18T10:00:00+00:00", provenance_status: "KNOWN" },
  { id: "s2", kind: "SUMMARY", origin: "UNTRUSTED_TOOL", source: "transformation", created_at: "2026-11-18T10:00:01+00:00", provenance_status: "KNOWN" },
  { id: "s3", kind: "AGENT_MESSAGE", origin: "UNTRUSTED_TOOL", agent_id: "agent_b", created_at: "2026-11-18T10:00:02+00:00", provenance_status: "KNOWN" },
  { id: "s4", kind: "TOOL_ARG", origin: "UNKNOWN", source: "reconstruction", created_at: "2026-11-18T10:00:03+00:00", provenance_status: "INFERRED" },
  { id: "s5", kind: "TOOL_RESULT", origin: "INTERNAL", source: "email.send", created_at: "2026-11-18T10:00:05+00:00", provenance_status: "KNOWN" },
];
const edges: SpanEdge[] = [
  { id: "e1", source: "s1", target: "s2", relationship: "SUMMARIZED_FROM", evidence_type: "EXPLICIT" },
  { id: "e2", source: "s2", target: "s3", relationship: "TRANSFERRED_TO_AGENT", evidence_type: "EXPLICIT" },
  { id: "e3", source: "s3", target: "s4", relationship: "USED_IN_TOOL_ARGUMENT", evidence_type: "INFERRED", inferred: true },
];
const decisions: Decision[] = [
  { call_id: "c1", tool: "email.send", risk_tier: "HIGH", decision: "BLOCK", created_at: "2026-11-18T10:00:04", agent_id: "agent_b", provenance_status: "INFERRED", arguments_redacted: { to: "[REDACTED_EMAIL]" }, policy_id: "block-untrusted-influence" },
  { call_id: "c2", tool: "email.send", risk_tier: "HIGH", decision: "ALLOW", created_at: "2026-11-18T10:00:06", agent_id: "agent_a", provenance_status: "KNOWN", arguments_redacted: { to: "[REDACTED_EMAIL]" } },
  { call_id: "c3", tool: "http.get", risk_tier: "MEDIUM", decision: "CONFIRM", created_at: "2026-11-18T10:00:08", agent_id: "agent_a", provenance_status: "UNKNOWN", arguments_redacted: { url: "[REDACTED_URL]" } },
];
const trace: Trace = {
  trace_id: "t1",
  label: "demo",
  kind: "attack",
  family: "multi_agent",
  source: "demo_seed",
  span_ids: ["s1", "s2", "s3", "s4", "s5"],
  call_ids: ["c1", "c2"],
  calls: [
    { call_ids: ["c1"], span_ids: ["s4"] },
    { call_ids: ["c2"], span_ids: ["s5"] },
  ],
};

describe("derive", () => {
  it("treats naive audit timestamps as UTC", () => {
    expect(parseTs("2026-11-18T10:00:04")).toBe(Date.UTC(2026, 10, 18, 10, 0, 4));
    expect(parseTs("2026-11-18T10:00:04+00:00")).toBe(Date.UTC(2026, 10, 18, 10, 0, 4));
  });

  it("bins every decision exactly once", () => {
    const { bins } = decisionTimeline(decisions, 4);
    const total = bins.reduce((s, b) => s + b.ALLOW + b.BLOCK + b.CONFIRM, 0);
    expect(total).toBe(3);
    expect(bins[0].BLOCK).toBe(1);
    expect(bins[3].CONFIRM).toBe(1);
  });

  it("computes gauges from real counts", () => {
    const g = riskGauges(decisions, edges);
    expect(g.blockRate).toBeCloseTo(1 / 3);
    expect(g.reviewLoad).toBeCloseTo(1 / 3);
    expect(g.unverifiedProvenance).toBeCloseTo(2 / 3);
    expect(g.inferredLineage).toBeCloseTo(1 / 3);
  });

  it("classifies destinations from redacted arguments only", () => {
    expect(destinationClass({ to: "[REDACTED_EMAIL]" })).toBe("Email recipient");
    expect(destinationClass({ url: "[REDACTED_URL]" })).toBe("Web endpoint");
    expect(destinationClass({ message_id: "1" })).toBe("No external destination");
    const flows = destinationFlows(decisions);
    expect(flows.tools).toEqual(["tool:email.send", "tool:http.get"]);
    const emailBlock = flows.links.find((l) => l.from === "tool:email.send" && l.decision === "BLOCK");
    expect(emailBlock?.count).toBe(1);
  });

  it("builds the trace DAG with categories and action nodes", () => {
    const g = buildTraceGraph(spans, edges, decisions, trace);
    const cat = Object.fromEntries(g.nodes.map((n) => [n.id, n.category]));
    expect(cat).toMatchObject({
      s1: "source",
      s2: "transform",
      s3: "agent",
      s4: "output",
      s5: "output",
      "call:c1": "action",
      "call:c2": "action",
    });
    expect(g.nodes.find((n) => n.id === "call:c3")).toBeUndefined();
    expect(g.edges.find((e) => e.id === "e3")?.kind).toBe("inferred");
    expect(g.edges.find((e) => e.source === "s4" && e.target === "call:c1")?.kind).toBe("evaluated");
    expect(g.edges.find((e) => e.source === "call:c2" && e.target === "s5")?.kind).toBe("executed");
  });

  it("counts decisions reachable from each source", () => {
    const g = buildTraceGraph(spans, edges, decisions, trace);
    const flows = flowsBySource(g.nodes, g.edges);
    expect(flows).toHaveLength(1);
    expect(flows[0].counts).toEqual({ BLOCK: 1 });
  });

  it("orders timeline events by time", () => {
    const g = buildTraceGraph(spans, edges, decisions, trace);
    const ev = traceTimeline(g.nodes);
    expect(ev[0].type).toBe("TOOL_RESULT");
    expect(ev.map((e) => e.at)).toEqual([...ev.map((e) => e.at)].sort((a, b) => a - b));
    expect(ev.some((e) => e.type === "BLOCK email.send")).toBe(true);
  });

  it("lays the DAG out left to right with labelled columns", () => {
    const g = buildTraceGraph(spans, edges, decisions, trace);
    const l = layoutDag(g.nodes, g.edges);
    expect(l.positions.get("s1")!.x).toBeLessThan(l.positions.get("s2")!.x);
    expect(l.positions.get("s4")!.x).toBeLessThan(l.positions.get("call:c1")!.x);
    expect(l.columns[0].label).toContain("Sources");
    expect(curvePath(l.paths[0].points)).toMatch(/^M/);
  });
});
