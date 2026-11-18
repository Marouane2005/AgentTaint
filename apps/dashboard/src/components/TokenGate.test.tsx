import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TokenGate } from "./TokenGate";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("TokenGate", () => {
  it("asks for the dashboard token only when the API answers 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 401 }));
    render(<TokenGate />);
    expect(await screen.findByText("Dashboard token required")).toBeInTheDocument();
    expect(screen.getByLabelText("Dashboard token")).toHaveAttribute("type", "password");
  });

  it("stays hidden when the API is reachable", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("agenttaint.dashboardToken", "typed-token");
    render(<TokenGate />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const init = fetchMock.mock.calls[0][1] as { headers: Record<string, string> };
    expect(init.headers["X-AgentTaint-Token"]).toBe("typed-token");
    expect(screen.queryByText("Dashboard token required")).toBeNull();
  });
});
