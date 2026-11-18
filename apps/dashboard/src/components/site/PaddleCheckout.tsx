"use client";

import { useEffect, useState } from "react";
import { PADDLE_CLIENT_TOKEN, PADDLE_PRICE_ID, PRO_PRICE_LABEL } from "@/lib/site";

type PaddleGlobal = {
  Initialize: (opts: { token: string }) => void;
  Checkout: { open: (opts: { items: { priceId: string; quantity: number }[] }) => void };
};

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const SCRIPT_SRC = "https://cdn.paddle.com/paddle/v2/paddle.js";
let initialized = false;

function loadPaddle(): Promise<PaddleGlobal> {
  return new Promise((resolve, reject) => {
    if (window.Paddle) return resolve(window.Paddle);
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error("Paddle missing")));
    s.onerror = () => reject(new Error("Could not load checkout"));
    document.head.appendChild(s);
  });
}

/** Paddle.js overlay checkout for AgentTaint Pro. Renders nothing without a token. */
export function PaddleCheckout() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!PADDLE_CLIENT_TOKEN) return;
    loadPaddle()
      .then((p) => {
        if (!initialized) {
          p.Initialize({ token: PADDLE_CLIENT_TOKEN });
          initialized = true;
        }
        setReady(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (!PADDLE_CLIENT_TOKEN) return null;
  return (
    <>
      <button
        className="btn"
        disabled={!ready}
        onClick={() =>
          window.Paddle?.Checkout.open({ items: [{ priceId: PADDLE_PRICE_ID, quantity: 1 }] })
        }
      >
        Subscribe · {PRO_PRICE_LABEL}
      </button>
      {error ? <p className="form-msg error">{error}</p> : null}
      <p className="fine">
        Checkout by Paddle, our merchant of record. Cancel anytime; 14-day refund policy.
      </p>
    </>
  );
}
