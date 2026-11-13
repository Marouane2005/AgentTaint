import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProvenanceGraph } from "./ProvenanceGraph";

describe("ProvenanceGraph", () => {
  it("renders empty state", () => {
    render(<ProvenanceGraph nodes={[]} edges={[]} />);
    expect(screen.getByText(/No provenance spans yet/i)).toBeInTheDocument();
  });

  it("renders nodes with provenance status labels and selection", () => {
    render(
      <ProvenanceGraph
        nodes={[
          {
            id: "a",
            kind: "TOOL_RESULT",
            provenance_status: "KNOWN",
            origin: "UNTRUSTED_TOOL",
            agent_id: "agent_a",
          },
          {
            id: "b",
            kind: "SUMMARY",
            provenance_status: "INFERRED",
            origin: "UNTRUSTED_TOOL",
            agent_id: "agent_a",
          },
          {
            id: "c",
            kind: "GAP",
            provenance_status: "UNKNOWN",
            origin: "UNKNOWN",
            agent_id: null,
          },
        ]}
        edges={[
          {
            id: "e1",
            source: "a",
            target: "b",
            relationship: "SUMMARIZED_FROM",
            evidence_type: "EXPLICIT",
            inferred: false,
            legend: "EXPLICIT — instrumented / verified link",
          },
          {
            id: "e2",
            source: "b",
            target: "c",
            relationship: "GAP_FROM",
            evidence_type: "INFERRED",
            inferred: true,
            legend: "INFERRED — reconstruction evidence only",
          },
        ]}
      />,
    );
    expect(screen.getByLabelText(/Provenance graph/i)).toBeInTheDocument();
    expect(screen.getAllByText("KNOWN").length).toBeGreaterThan(0);
    expect(screen.getAllByText("INFERRED").length).toBeGreaterThan(0);
    expect(screen.getByText(/gaps\/unknown/i)).toBeInTheDocument();

    const node = screen.getByText("TOOL_RESULT");
    fireEvent.click(node);
    expect(screen.getByText(/Selection details/i)).toBeInTheDocument();
    expect(screen.getByText(/UNTRUSTED_TOOL/)).toBeInTheDocument();
  });
});
