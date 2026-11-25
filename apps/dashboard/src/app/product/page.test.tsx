import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
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
