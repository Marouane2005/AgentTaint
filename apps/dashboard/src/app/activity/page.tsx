"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHint } from "@/components/PageHint";
import { Skeleton } from "@/components/Skeleton";
import { fetchDecisions, type Decision } from "@/lib/api";
import { formatUtcTime, parseTs } from "@/lib/derive";

const POLL_MS = 5000;

/**
 * Recent gateway decisions, polled from the audit store.
 * The list is whatever the server returned on the last successful read.
 */
export default function ActivityPage() {
  const [items, setItems] = useState<Decision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [updated, setUpdated] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const page = await fetchDecisions({ limit: 40, sort: "created_at", order: "desc" });
      setItems(page.items as Decision[]);
      setError(null);
      setUpdated(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <div className="console">
      <PageHint id="activity" title="Live activity">
        Each row is a tool call the gateway already judged. The page asks the audit store again
        every few seconds. It does not invent events while the request is in flight.
      </PageHint>
      <div className="console-head">
        <div>
          <p className="eyebrow">Audit stream</p>
          <h1>Live activity</h1>
          <p className="sub">
            Polled from <span className="mono">GET /api/v1/decisions</span>
            {updated ? ` · last read ${formatUtcTime(parseTs(updated))} UTC` : ""}.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      {!loaded ? <Skeleton label="Loading activity" rows={5} /> : null}
      {loaded && !items.length ? (
        <div className="empty">No decisions in the audit store yet.</div>
      ) : null}
      <ul className="activity-list">
        {items.map((row) => (
          <li key={row.call_id} className="activity-item">
            <div className="activity-top">
              <span className={`dec ${row.decision}`}>{row.decision}</span>
              <strong className="mono">{row.tool}</strong>
              <span className="dim">{row.risk_tier}</span>
              <span className="mono dim">{row.policy_id || "—"}</span>
              <time className="mono dim" dateTime={row.created_at}>
                {formatUtcTime(parseTs(row.created_at))} UTC
              </time>
            </div>
            <p>{row.explanation || "No explanation recorded."}</p>
            <div className="activity-meta mono small">
              provenance {row.provenance_status || "—"} · args{" "}
              {JSON.stringify(row.arguments_redacted || {})} · hash {row.arguments_hash || "—"}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
