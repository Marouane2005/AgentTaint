import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import ProductPage from "./page";

afterEach(cleanup);

describe("Product page", () => {
  it("shows Paddle-matching price, waitlist fallback, contact and legal links", () => {
    render(<ProductPage />);
    expect(screen.getByText("$15.00")).toBeInTheDocument();
    expect(screen.getByText(/USD\/month/)).toBeInTheDocument();
    // No PADDLE_CLIENT_TOKEN in tests: the waitlist replaces checkout.
    expect(screen.getAllByRole("button", { name: /Join Pro waitlist/ }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Subscribe/ })).toBeNull();
    for (const name of ["Terms of Service", "Privacy Policy", "Refund Policy"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link", { name: "maroozi2018@gmail.com" })[0]).toHaveAttribute(
      "href",
      "mailto:maroozi2018@gmail.com",
    );
  });
});
