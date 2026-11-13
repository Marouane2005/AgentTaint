"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import {
  clearSession,
  fetchDecisions,
  fetchHealth,
  fetchOverview,
  seedDemo,
} from "@/lib/api";

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 1000) / 10;
}

export default function OverviewPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchOverview>> | null>(
    null,
  );
  const [events, setEvents] = useState<
    Awaited<ReturnType<typeof fetchDecisions>>["items"]
  >([]);
  const [health, setHealth] = useState<string>("checking…");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [overview, h, decisions] = await Promise.all([
        fetchOverview(),
        fetchHealth(),
        fetchDecisions(),
      ]);
      setData(overview);
      setHealth(h.status);
      setEvents(decisions.items.slice(0, 8));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
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
  const total = Number(decisions.total || 0);
  const allow = Number(decisions.ALLOW || 0);
  const block = Number(decisions.BLOCK || 0);
  const confirm = Number(decisions.CONFIRM || 0);

  const mix = useMemo(
    () => ({
      allow: pct(allow, total),
      block: pct(block, total),
      confirm: pct(confirm, total),
    }),
    [allow, block, confirm, total],
  );

  return (
    <>
      <div className="topbar">
        <div>
          <p className="eyebrow">Security operations</p>
          <h1>Overview</h1>
          <p>
            Live counters from the AgentTaint audit store and provenance registry.
            Demo seed executes a labeled simulated scenario through the real
            SecurityGateway — decisions are never invented by the UI.
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

      {loading ? <div className="loading">Loading control-plane metrics…</div> : null}

      <div className="grid stats">
        <div className="stat allow">
          <div className="label">ALLOW</div>
          <div className="value">{allow}</div>
          <div className="hint">{mix.allow}% of events</div>
        </div>
        <div className="stat block">
          <div className="label">BLOCK</div>
          <div className="value">{block}</div>
          <div className="hint">{mix.block}% of events</div>
        </div>
        <div className="stat confirm">
          <div className="label">CONFIRM</div>
          <div className="value">{confirm}</div>
          <div className="hint">{mix.confirm}% of events</div>
        </div>
        <div className="stat info">
          <div className="label">Events</div>
          <div className="value">{total}</div>
          <div className="hint">audit store records</div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: "1rem" }}>
        <div className="panel-head">
          <h2>Decision mix</h2>
          <span className="panel-meta">session totals</span>
        </div>
        <div className="mix-bar" aria-hidden={!total}>
          {total ? (
            <>
              <span className="allow" style={{ width: `${mix.allow}%` }} />
              <span className="block" style={{ width: `${mix.block}%` }} />
              <span className="confirm" style={{ width: `${mix.confirm}%` }} />
            </>
          ) : null}
        </div>
        <div className="mix-legend">
          <span>
            <i style={{ background: "var(--allow)" }} />
            ALLOW {allow}
          </span>
          <span>
            <i style={{ background: "var(--block)" }} />
            BLOCK {block}
          </span>
          <span>
            <i style={{ background: "var(--confirm)" }} />
            CONFIRM {confirm}
          </span>
        </div>
      </div>

      <div className="grid overview">
        <div className="panel">
          <div className="panel-head">
            <h2>Recent security events</h2>
            <span className="panel-meta">from audit store</span>
          </div>
          {!events.length ? (
            <div className="empty">
              No events yet. Seed the simulated demo or connect a live proxy.
            </div>
          ) : (
            <div className="event-list">
              {events.map((row) => (
                <div className="event-item" key={String(row.call_id)}>
                  <span className={`pill ${String(row.decision)}`}>
                    {String(row.decision)}
                  </span>
                  <div>
                    <div className="title mono">{String(row.tool)}</div>
                    <div className="sub">
                      policy={String(row.policy_id || "—")} · agent=
                      {String(row.agent_id || "—")} · risk=
                      {String(row.risk_tier)}
                    </div>
                  </div>
                  <div className="when mono">
                    {String(row.latency_ms ?? "—")} ms
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>System & provenance</h2>
          </div>
          <div className="status-grid">
            <div className="status-row">
              <span className="k">API health</span>
              <span className="v">
                <span
                  className={`dot ${health === "ok" ? "ok" : "err"}`}
                  aria-hidden
                />
                <span className="mono">{health}</span>
              </span>
            </div>
            <div className="status-row">
              <span className="k">Session mode</span>
              <span className="v mono">{data?.session?.mode || "—"}</span>
            </div>
            <div className="status-row">
              <span className="k">Spans</span>
              <span className="v">{graph.spans}</span>
            </div>
            <div className="status-row">
              <span className="k">Edges</span>
              <span className="v">{graph.edges}</span>
            </div>
            <div className="status-row">
              <span className="k">Inferred edges</span>
              <span className="v" style={{ color: "var(--confirm)" }}>
                {graph.inferred_edges}
              </span>
            </div>
            <div className="status-row">
              <span className="k">Gap markers</span>
              <span className="v" style={{ color: "var(--unknown)" }}>
                {graph.gap_spans}
              </span>
            </div>
            <div className="status-row">
              <span className="k">Data path</span>
              <span className="v mono" style={{ fontSize: "0.75rem" }}>
                {String(data?.system?.data_dir || "—")}
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
