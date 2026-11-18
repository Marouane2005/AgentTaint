"use client";

import { useEffect, useState } from "react";

let cached: boolean | null = null;

/** True when the control plane reports AGENTTAINT_DEMO_MODE (public demo). */
export function useDemoMode(): boolean {
  const [demo, setDemo] = useState<boolean>(cached ?? false);
  useEffect(() => {
    if (cached !== null) return;
    fetch("/api/v1/health", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        cached = Boolean(h && h.demo_mode);
        setDemo(cached);
      })
      .catch(() => setDemo(false));
  }, []);
  return demo;
}
