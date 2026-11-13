"use client";

import { useCallback, useEffect, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import { clearSession, fetchHealth, fetchOverview, seedDemo } from "@/lib/api";

export default function OverviewPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchOverview>> | null>(
    null,
  );
  const [health, setHealth] = useState<string>("checking…");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [overview, h] = await Promise.all([fetchOverview(), fetchHealth()]);
      setData(overview);
      setHealth(h.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSeed() {
    setBusy(true);
    try {
      await seedDemo();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onClear() {
    setBusy(true);
    try {
      await clearSession();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const decisions = data?.decisions || { ALLOW: 0, BLOCK: 0, CONFIRM: 0, total: 0 };
  const graph = data?.graph || { spans: 0, edges: 0, inferred_edges: 0, gap_spans: 0 };

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Overview</h1>
          <p>
            Live counters from the AgentTaint audit store and provenance registry.
            Demo seed runs a simulated scenario through the real SecurityGateway.
          </p>
        </div>
        <div className="actions">
          <button className="btn secondary" onClick={onClear} disabled={busy}>
            Clear session
          </button>
          <button className="btn" onClick={onSeed} disabled={busy}>
            {busy ? "Seeding…" : "Seed demo session"}
          </button>
        </div>
      </div>

      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />

      <div className="grid stats">
        <div className="stat allow">
          <div className="label">ALLOW</div>
          <div className="value">{decisions.ALLOW ?? 0}</div>
        </div>
        <div className="stat block">
          <div className="label">BLOCK</div>
          <div className="value">{decisions.BLOCK ?? 0}</div>
        </div>
        <div className="stat confirm">
          <div className="label">CONFIRM</div>
          <div className="value">{decisions.CONFIRM ?? 0}</div>
        </div>
        <div className="stat">
          <div className="label">Events</div>
          <div className="value">{decisions.total ?? 0}</div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: "1rem" }}>
        <h2>System status</h2>
        <div className="legend">
          <div>
            <strong>API health</strong>
            <span className="mono">{health}</span>
          </div>
          <div>
            <strong>Spans / edges</strong>
            <span>
              {graph.spans} spans · {graph.edges} edges · {graph.inferred_edges} inferred ·{" "}
              {graph.gap_spans} gaps
            </span>
          </div>
          <div>
            <strong>Data path</strong>
            <span className="mono">{String(data?.system?.data_dir || "—")}</span>
          </div>
        </div>
      </div>
    </>
  );
}
