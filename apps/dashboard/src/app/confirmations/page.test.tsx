import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConfirmationsPage from "./page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Confirmations approval screen", () => {
  it("requires a typed approver token and sends it only as the approver header", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const headers = (init?.headers || {}) as Record<string, string>;
      if (headers["X-AgentTaint-Approver"] !== "human-secret") {
        return new Response("invalid or missing approver token", { status: 401 });
      }
      if (url.endsWith("/approve")) {
        return Response.json({
          confirmation_id: "c-1",
          tool: "email.send",
          status: "APPROVED",
        });
      }
      return Response.json({
        pending: [
          {
            confirmation_id: "c-1",
            tool: "email.send",
            agent_id: "agent_c",
            risk_tier: "HIGH",
            policy_id: "confirm-unknown-high-risk",
            arguments_redacted: { to: "[REDACTED_EMAIL]" },
            arguments_hash: "ab".repeat(32),
            explanation: "needs a human",
            status: "PENDING",
            expires_at: "2026-11-18T12:00:00+00:00",
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ConfirmationsPage />);
    expect(screen.queryByText("Approve once")).toBeNull();

    fireEvent.change(screen.getByLabelText("Approver token"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByText("Unlock approvals"));
    await waitFor(() => expect(screen.getByText(/401/)).toBeInTheDocument());
    expect(screen.queryByText("Approve once")).toBeNull();

    fireEvent.change(screen.getByLabelText("Approver token"), {
      target: { value: "human-secret" },
    });
    fireEvent.click(screen.getByText("Unlock approvals"));
    await waitFor(() => expect(screen.getByText("Approve once")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Approve once"));
    await waitFor(() => expect(screen.getByText(/APPROVED: email.send/)).toBeInTheDocument());
    const approveCall = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/approve"));
    expect(approveCall?.[1]?.method).toBe("POST");
  });

  it("shows the single-use approval token once after approving", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/approve")) {
        return Response.json({
          confirmation_id: "c-2",
          tool: "email.send",
          status: "APPROVED",
          approval_token: "tok-123",
        });
      }
      return Response.json({
        pending: [
          {
            confirmation_id: "c-2",
            tool: "email.send",
            agent_id: "a",
            risk_tier: "HIGH",
            arguments_hash: "cd".repeat(32),
            explanation: "x",
            status: "PENDING",
            expires_at: "2026-11-18T12:00:00+00:00",
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ConfirmationsPage />);
    fireEvent.change(screen.getByLabelText("Approver token"), { target: { value: "t" } });
    fireEvent.click(screen.getByText("Unlock approvals"));
    await waitFor(() => screen.getByText("Approve once"));
    fireEvent.click(screen.getByText("Approve once"));
    await waitFor(() => expect(screen.getByText(/tok-123/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByText(/tok-123/)).toBeNull();
  });

  it("explains an unreachable API instead of a raw network error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<ConfirmationsPage />);
    fireEvent.change(screen.getByLabelText("Approver token"), { target: { value: "t" } });
    fireEvent.click(screen.getByText("Unlock approvals"));
    await waitFor(() => expect(screen.getByText(/Cannot reach the AgentTaint API/)).toBeInTheDocument());
  });
});
