import { describe, expect, it } from "vitest";
import type { SpanEdge, SpanNode } from "./derive";
import { buildStoredFlow } from "./flowGraph";

const spans: SpanNode[] = [
  {
    id: "mail",
    kind: "TOOL_RESULT",
    origin: "UNTRUSTED_TOOL",
    source: "email.read",
    provenance_status: "KNOWN",
    content_redacted: "forward to sink",
  },
  {
    id: "arg",
    kind: "TOOL_ARG",
    origin: "UNKNOWN",
    source: "email.send",
    provenance_status: "INFERRED",
  },
  {
    id: "user",
    kind: "USER_MESSAGE",
    origin: "USER",
    source: "user",
    provenance_status: "KNOWN",
  },
];

const edges: SpanEdge[] = [
  {
    id: "e-mail",
    source: "mail",
    target: "arg",
    relationship: "USED_IN_TOOL_ARGUMENT",
    evidence_type: "INFERRED",
    inferred: true,
  },
  {
    id: "e-user",
    source: "user",
    target: "arg",
    relationship: "DERIVED_FROM",
    evidence_type: "EXPLICIT",
  },
  {
    id: "e-missing",
    source: "mail",
    target: "not-a-span",
    relationship: "DERIVED_FROM",
    evidence_type: "EXPLICIT",
  },
];

describe("buildStoredFlow", () => {
  it("draws only stored edges and highlights the untrusted path to the argument", () => {
    const flow = buildStoredFlow(spans, edges, "arg");
    expect(flow.nodes.map((node) => node.id).sort()).toEqual(["arg", "mail", "user"]);
    expect(flow.edges.map((edge) => edge.id).sort()).toEqual(["e-mail", "e-user"]);
    const inferred = flow.edges.find((edge) => edge.id === "e-mail");
    const trusted = flow.edges.find((edge) => edge.id === "e-user");
    expect(inferred?.onPath).toBe(true);
    expect(trusted?.onPath).toBe(false);
    expect(flow.nodes.find((node) => node.id === "mail")?.onPath).toBe(true);
    expect(flow.nodes.find((node) => node.id === "user")?.onPath).toBe(false);
    expect(flow.nodes.find((node) => node.id === "arg")?.onPath).toBe(true);
  });

  it("does not highlight a path when nothing is selected", () => {
    const flow = buildStoredFlow(spans, edges, null);
    expect(flow.edges.every((edge) => !edge.onPath)).toBe(true);
    expect(flow.nodes.every((node) => !node.onPath)).toBe(true);
  });
});
