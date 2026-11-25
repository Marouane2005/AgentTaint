import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProductPage from "./page";
import TermsPage from "../terms/page";
import RefundsPage from "../refunds/page";

afterEach(cleanup);

describe("Product page", () => {
  it("presents AgentTaint as free Apache-2.0 open source with optional hosted support waitlist", () => {
    render(<ProductPage />);
    expect(screen.getAllByText(/Free/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Apache[- ]2\.0/i).length).toBeGreaterThan(0);
    expect(screen.getByText("$15.00")).toBeInTheDocument();
    expect(screen.getByText(/USD\/month/)).toBeInTheDocument();
    expect(screen.getByText(/Hosted Support \(Optional\)/)).toBeInTheDocument();
    // No PADDLE_CLIENT_TOKEN in tests: the waitlist replaces checkout.
    expect(screen.getAllByRole("button", { name: /Join waitlist/ }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Subscribe/ })).toBeNull();
    for (const name of ["Terms of Service", "Privacy Policy", "Refund Policy"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link", { name: "maroozi2018@gmail.com" })[0]).toHaveAttribute(
      "href",
      "mailto:maroozi2018@gmail.com",
    );
  });

  it("shows the PyPI install command, 1.0.0 badge, doctor check, and proxy config", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ProductPage />);

    const installLinks = screen.getAllByRole("link", { name: "Install" });
    expect(installLinks.map((link) => link.getAttribute("href"))).toEqual([
      "/product#install",
      "#install",
    ]);

    const section = document.getElementById("install");
    expect(section).not.toBeNull();
    expect(section?.textContent).toContain("pip install agenttaint");
    expect(section?.textContent).toContain("1.0.0");
    expect(section?.textContent).toContain(
      'agenttaint init ~/agenttaint --backend "npx -y @modelcontextprotocol/server-filesystem $HOME/projects"',
    );
    expect(section?.textContent).toContain(
      "agenttaint doctor --config ~/agenttaint/agenttaint.yaml",
    );
    expect(section?.textContent).toContain(
      '["proxy", "--config", "/home/you/agenttaint/agenttaint.yaml"]',
    );
    expect(section?.textContent).toContain(
      "agenttaint connect claude-desktop --config ~/agenttaint/agenttaint.yaml",
    );

    expect(screen.getByRole("link", { name: "PyPI" })).toHaveAttribute(
      "href",
      "https://pypi.org/project/agenttaint/",
    );
    expect(screen.getByRole("link", { name: "v1.0.0 release" })).toHaveAttribute(
      "href",
      "https://github.com/Marouane2005/AgentTaint/releases/tag/v1.0.0",
    );
    expect(
      screen.getByRole("heading", { name: "Open source & optional hosted support" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("pip install agenttaint");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("reconciles terms and refund pages with Apache-2.0 open source", () => {
    render(<TermsPage />);
    expect(screen.getAllByText(/Apache License 2\.0/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/AgentTaint Pro/i)).toBeNull();
    cleanup();
    render(<RefundsPage />);
    expect(screen.getByText(/Apache License 2\.0/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Hosted Support/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/AgentTaint Pro/i)).toBeNull();
  });
});
