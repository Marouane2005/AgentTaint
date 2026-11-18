"use client";

import { useEffect, useState } from "react";
import { getSessionToken, setSessionToken } from "@/lib/api";

/**
 * Shown only when the control plane answers 401 (AGENTTAINT_API_AUTH=required).
 * The operator types the dashboard read token; it lives in sessionStorage for
 * this tab and is never part of the build. It cannot approve confirmations:
 * approvals need the separate approver token on the Confirmations page.
 */
export function TokenGate() {
  const [needed, setNeeded] = useState(false);
  const [value, setValue] = useState("");

  useEffect(() => {
    const headers: HeadersInit = {};
    const typed = getSessionToken();
    if (typed) headers["X-AgentTaint-Token"] = typed;
    fetch("/api/v1/metrics/overview", { headers, cache: "no-store" })
      .then((res) => setNeeded(res.status === 401))
      .catch(() => setNeeded(false));
  }, []);

  if (!needed) return null;
  return (
    <form
      className="panel token-gate"
      onSubmit={(e) => {
        e.preventDefault();
        setSessionToken(value.trim());
        window.location.reload();
      }}
    >
      <strong>Dashboard token required</strong>
      <p className="muted">
        This control plane runs with authentication. Enter the dashboard token from your
        <code> .env</code> (AGENTTAINT_DASHBOARD_TOKEN). It is kept for this browser tab only.
      </p>
      <input
        type="password"
        autoComplete="off"
        aria-label="Dashboard token"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <button type="submit" className="btn">
        Unlock
      </button>
    </form>
  );
}
