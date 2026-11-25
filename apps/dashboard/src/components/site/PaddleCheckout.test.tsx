import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const MAILTO = "mailto:maroozi2018@gmail.com?subject=AgentTaint%20hosted%20support";
const SCRIPT_SRC = "https://cdn.paddle.com/paddle/v2/paddle.js";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.resetModules();
  delete window.Paddle;
  document.head.querySelectorAll('script[src*="paddle"]').forEach((node) => node.remove());
});

function prepare(flag: string, token = "live_test_token") {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", token);
  vi.stubEnv("NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED", flag);
}

async function renderCheckout() {
  const { PaddleCheckout } = await import("./PaddleCheckout");
  return render(<PaddleCheckout />);
}

function installPaddle(onInitialize?: () => void) {
  const open = vi.fn();
  const close = vi.fn();
  let onEvent: ((event: { name?: string }) => void) | undefined;
  window.Paddle = {
    Initialize: (opts) => {
      onEvent = opts.eventCallback;
      onInitialize?.();
    },
    Update: (opts) => {
      onEvent = opts.eventCallback;
    },
    Checkout: { open, close },
  };
  return {
    open,
    close,
    emit(name: string) {
      act(() => onEvent?.({ name }));
    },
  };
}

describe("Paddle checkout", () => {
  it.each(["", "false", "TRUE", "1"])("stays on email when the flag is %j", async (flag) => {
    prepare(flag);
    window.Paddle = { Initialize: vi.fn(), Checkout: { open: vi.fn(), close: vi.fn() } };
    await renderCheckout();
    expect(screen.getByRole("link", { name: "Request hosted support" })).toHaveAttribute("href", MAILTO);
    expect(screen.getByText(/arranged by email for now/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Subscribe/ })).toBeNull();
    expect(screen.queryByText(/merchant of record/i)).toBeNull();
    expect(screen.queryByText(/14-day refund/i)).toBeNull();
    expect(screen.queryByText(/isn't available right now/i)).toBeNull();
    expect(window.Paddle.Initialize).not.toHaveBeenCalled();
    expect(document.querySelector(`script[src="${SCRIPT_SRC}"]`)).toBeNull();
  });

  it("renders nothing when the client token is missing", async () => {
    prepare("true", "");
    const { container } = await renderCheckout();
    expect(container).toBeEmptyDOMElement();
    expect(document.querySelector(`script[src="${SCRIPT_SRC}"]`)).toBeNull();
  });

  it("opens Paddle when the flag is true", async () => {
    prepare("true");
    const paddle = installPaddle();
    await renderCheckout();
    const button = await screen.findByRole("button", {
      name: "Subscribe to Hosted Support · $15.00 USD/month",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(paddle.open).toHaveBeenCalledWith({
      items: [{ priceId: "pri_01m7r7zmmk1g29rp2y6t6px3mq", quantity: 1 }],
    });
    expect(screen.getByText(/merchant of record/i)).toBeInTheDocument();
    expect(screen.getByText(/14-day refund/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Request hosted support" })).toBeNull();
  });

  it("closes the overlay and falls back to email on checkout.error", async () => {
    prepare("true");
    const paddle = installPaddle();
    await renderCheckout();
    const button = await screen.findByRole("button", { name: /Subscribe to Hosted Support/ });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    paddle.emit("checkout.loaded");
    expect(paddle.close).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Subscribe to Hosted Support/ })).toBeInTheDocument();

    paddle.emit("checkout.error");
    expect(paddle.close).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Request hosted support" })).toHaveAttribute("href", MAILTO);
    expect(screen.getByRole("status")).toHaveTextContent(/isn't available right now/i);
    expect(screen.getByText(/arranged by email for now/i)).toBeInTheDocument();
    expect(screen.getByText(/merchant of record/i)).toBeInTheDocument();
    expect(screen.getByText(/14-day refund/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Subscribe/ })).toBeNull();
  });

  it("falls back when Paddle fails to initialise", async () => {
    prepare("true");
    const paddle = installPaddle(() => {
      throw new Error("seller not verified");
    });
    await renderCheckout();
    expect(await screen.findByRole("link", { name: "Request hosted support" })).toHaveAttribute(
      "href",
      MAILTO,
    );
    expect(paddle.close).toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent(/isn't available right now/i);
    expect(screen.queryByText(/seller not verified/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Subscribe/ })).toBeNull();
    expect(screen.getByText(/merchant of record/i)).toBeInTheDocument();
    expect(screen.getByText(/14-day refund/i)).toBeInTheDocument();
  });

  it("falls back when the checkout script fails to load", async () => {
    prepare("true");
    await renderCheckout();
    const script = await waitFor(() => {
      const node = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
      expect(node).toBeTruthy();
      return node as HTMLScriptElement;
    });
    act(() => {
      script.onerror?.(new Event("error"));
    });
    expect(await screen.findByRole("link", { name: "Request hosted support" })).toHaveAttribute(
      "href",
      MAILTO,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/isn't available right now/i);
    expect(screen.queryByText(/Could not load checkout/)).toBeNull();
    expect(screen.getByText(/merchant of record/i)).toBeInTheDocument();
  });

  it("falls back when opening the overlay throws", async () => {
    prepare("true");
    const paddle = installPaddle();
    paddle.open.mockImplementation(() => {
      throw new Error("overlay failed");
    });
    await renderCheckout();
    const button = await screen.findByRole("button", { name: /Subscribe to Hosted Support/ });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(paddle.close).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Request hosted support" })).toHaveAttribute("href", MAILTO);
    expect(screen.queryByText(/overlay failed/)).toBeNull();
    expect(screen.getByText(/14-day refund/i)).toBeInTheDocument();
  });
});
