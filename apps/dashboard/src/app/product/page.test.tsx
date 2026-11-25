import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProductPage from "./page";
import TermsPage from "../terms/page";
import RefundsPage from "../refunds/page";

const SUPPORT_MAILTO = "mailto:maroozi2018@gmail.com?subject=AgentTaint%20hosted%20support";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
  delete window.Paddle;
  document.head.querySelectorAll('script[src*="paddle"]').forEach((node) => node.remove());
});

async function renderFreshProduct() {
  vi.resetModules();
  const { default: Page } = await import("./page");
  return render(<Page />);
}

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
    expect(screen.queryByRole("link", { name: "Request hosted support" })).toBeNull();
    const pricing = within(document.getElementById("pricing") as HTMLElement);
    expect(pricing.queryByText(/merchant of record/i)).toBeNull();
    expect(pricing.queryByText(/14-day refund/i)).toBeNull();
    for (const name of ["Terms of Service", "Privacy Policy", "Refund Policy"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link", { name: "maroozi2018@gmail.com" })[0]).toHaveAttribute(
      "href",
      "mailto:maroozi2018@gmail.com",
    );
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

  it.each(["", "false", "TRUE"])(
    "requests hosted support by email when checkout is not enabled (%j)",
    async (flag) => {
      vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "live_test_token");
      vi.stubEnv("NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED", flag);
      await renderFreshProduct();
      const pricing = within(document.getElementById("pricing") as HTMLElement);
      const link = pricing.getByRole("link", { name: "Request hosted support" });
      expect(link).toHaveAttribute("href", SUPPORT_MAILTO);
      expect(link.className).toContain("btn");
      expect(pricing.getByText(/arranged by email for now/i)).toBeInTheDocument();
      expect(pricing.queryByRole("button", { name: /Subscribe/ })).toBeNull();
      expect(pricing.queryByText(/merchant of record/i)).toBeNull();
      expect(pricing.queryByText(/14-day refund/i)).toBeNull();
      expect(document.querySelector('script[src*="paddle"]')).toBeNull();
    },
  );

  it("keeps Paddle checkout and the refund wording when the flag is true", async () => {
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "live_test_token");
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED", "true");
    const open = vi.fn();
    window.Paddle = {
      Initialize: vi.fn(),
      Checkout: { open, close: vi.fn() },
    };
    await renderFreshProduct();
    const pricing = within(document.getElementById("pricing") as HTMLElement);
    const button = await pricing.findByRole("button", {
      name: "Subscribe to Hosted Support · $15.00 USD/month",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(open).toHaveBeenCalledWith({
      items: [{ priceId: "pri_01m7r7zmmk1g29rp2y6t6px3mq", quantity: 1 }],
    });
    expect(pricing.getByText(/merchant of record/i)).toBeInTheDocument();
    expect(pricing.getByText(/14-day refund/i)).toBeInTheDocument();
    expect(pricing.queryByRole("link", { name: "Request hosted support" })).toBeNull();
    expect(pricing.queryByText(/arranged by email for now/i)).toBeNull();
  });
});
