"use client";

import { useEffect, useState } from "react";
import {
  hostedSupportMailto,
  PADDLE_CHECKOUT_ENABLED,
  PADDLE_CLIENT_TOKEN,
  PADDLE_PRICE_ID,
  SUPPORT_PRICE_LABEL,
} from "@/lib/site";

type PaddleEvent = { name?: string };

type PaddleGlobal = {
  Initialize: (opts: { token: string; eventCallback?: (event: PaddleEvent) => void }) => void;
  Update?: (opts: { eventCallback?: (event: PaddleEvent) => void }) => void;
  Checkout: {
    open: (opts: { items: { priceId: string; quantity: number }[] }) => void;
    close?: () => void;
  };
};

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const SCRIPT_SRC = "https://cdn.paddle.com/paddle/v2/paddle.js";
const CHECKOUT_UNAVAILABLE =
  "Checkout isn't available right now. Email us and we'll arrange hosted support.";

let initialized = false;
let loading: Promise<PaddleGlobal> | null = null;

function loadPaddle(): Promise<PaddleGlobal> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error("Paddle missing")));
    s.onerror = () => reject(new Error("Could not load checkout"));
    document.head.appendChild(s);
  });
  loading.catch(() => {
    loading = null;
  });
  return loading;
}

function closeCheckout() {
  try {
    window.Paddle?.Checkout.close?.();
  } catch {
    /* The overlay may already be gone. */
  }
}

function PaddleFinePrint() {
  return (
    <p className="fine">
      Optional hosted support processed by Paddle, our merchant of record. AgentTaint itself is
      free open source (Apache-2.0). Cancel anytime; 14-day refund policy.
    </p>
  );
}

function EmailSupport({ notice }: { notice?: string }) {
  return (
    <>
      {notice ? (
        <p className="fine" role="status">
          {notice}
        </p>
      ) : null}
      <a className="btn" href={hostedSupportMailto()}>
        Request hosted support
      </a>
      <p className="fine">Hosted support is arranged by email for now.</p>
    </>
  );
}

/** Paddle.js overlay for optional hosted support, or email when checkout is off. */
export function PaddleCheckout() {
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!PADDLE_CHECKOUT_ENABLED || !PADDLE_CLIENT_TOKEN) return;
    let cancelled = false;
    const onEvent = (event: PaddleEvent) => {
      if (event?.name !== "checkout.error") return;
      closeCheckout();
      setUnavailable(true);
    };
    loadPaddle()
      .then((paddle) => {
        if (cancelled) return;
        if (!initialized) {
          paddle.Initialize({ token: PADDLE_CLIENT_TOKEN, eventCallback: onEvent });
          initialized = true;
        } else {
          paddle.Update?.({ eventCallback: onEvent });
        }
        setReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        closeCheckout();
        setUnavailable(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!PADDLE_CLIENT_TOKEN) return null;

  if (!PADDLE_CHECKOUT_ENABLED) {
    return (
      <div className="support-cta">
        <EmailSupport />
      </div>
    );
  }

  if (unavailable) {
    return (
      <div className="support-cta">
        <EmailSupport notice={CHECKOUT_UNAVAILABLE} />
        <PaddleFinePrint />
      </div>
    );
  }

  return (
    <div className="support-cta">
      <button
        className="btn"
        type="button"
        disabled={!ready}
        onClick={() => {
          try {
            window.Paddle?.Checkout.open({
              items: [{ priceId: PADDLE_PRICE_ID, quantity: 1 }],
            });
          } catch {
            closeCheckout();
            setUnavailable(true);
          }
        }}
      >
        Subscribe to Hosted Support · {SUPPORT_PRICE_LABEL}
      </button>
      <PaddleFinePrint />
    </div>
  );
}
