import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TraceGraph } from "./TraceGraph";
import type { ViewEdge, ViewNode } from "@/lib/derive";

const nodes: ViewNode[] = [
  { id: "a", category: "source", label: "email.read", sublabel: "TOOL_RESULT · UNTRUSTED_TOOL" },
  { id: "b", category: "output", label: "reconstruction", sublabel: "TOOL_ARG · UNKNOWN" },
  { id: "call:c", category: "action", label: "email.send", sublabel: "BLOCK · HIGH", decision: "BLOCK" },
];
const edges: ViewEdge[] = [
  { id: "e1", source: "a", target: "b", label: "USED_IN_TOOL_ARGUMENT", kind: "inferred" },
  { id: "e2", source: "b", target: "call:c", label: "EVALUATED", kind: "evaluated" },
];

describe("TraceGraph", () => {
  it("renders nodes, edge labels, legend, zoom and flows popover", () => {
    const onSelect = vi.fn();
    render(<TraceGraph nodes={nodes} edges={edges} selectedId={null} onSelect={onSelect} />);
    expect(screen.getByText("USED_IN_TOOL_ARGUMENT")).toBeInTheDocument();
    expect(screen.getByText("Node types")).toBeInTheDocument();
    expect(screen.getByText("Flows by source")).toBeInTheDocument();
    expect(screen.getByText("BLOCK 1")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Zoom in"));
    fireEvent.click(screen.getByLabelText("action email.send"));
    expect(onSelect).toHaveBeenCalledWith("call:c");
  });

  it("shows an empty state", () => {
    render(<TraceGraph nodes={[]} edges={[]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText(/No spans for this trace/)).toBeInTheDocument();
  });
});
