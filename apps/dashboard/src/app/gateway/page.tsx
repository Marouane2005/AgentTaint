"use client";

import { useEffect, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchDecisions } from "@/lib/api";

export default function GatewayPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchDecisions>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetchDecisions()
      .then((payload) => {
        setData(payload);
        if (payload.items[0]) {
          setSelected(String(payload.items[0].call_id));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const items = data?.items || [];
  const active = items.find((i) => String(i.call_id) === selected);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Security Gateway</h1>
          <p>
            Intercepted MCP tool decisions from the audit store — hashes and redacted
            arguments only. The dashboard never bypasses enforcement.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      <div className="two-col">
        <div className="panel">
          <h2>Audit trail</h2>
          {!items.length ? (
            <div className="empty">No decisions yet. Seed the demo session.</div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Decision</th>
                    <th>Tool</th>
                    <th>Risk</th>
                    <th>Policy</th>
                    <th>Agent</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr
                      key={String(row.call_id)}
                      onClick={() => setSelected(String(row.call_id))}
                      style={{
                        cursor: "pointer",
                        background:
                          selected === String(row.call_id) ? "#eef7f4" : undefined,
                      }}
                    >
                      <td>
                        <span className={`pill ${String(row.decision)}`}>
                          {String(row.decision)}
                        </span>
                      </td>
                      <td className="mono">{String(row.tool)}</td>
                      <td>{String(row.risk_tier)}</td>
                      <td className="mono">{String(row.policy_id || "—")}</td>
                      <td className="mono">{String(row.agent_id || "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="panel">
          <h2>Decision detail</h2>
          {!active ? (
            <div className="empty">Select a decision.</div>
          ) : (
            <div className="legend">
              <div>
                <strong>Call</strong>
                <span className="mono">{String(active.call_id)}</span>
              </div>
              <div>
                <strong>Args hash</strong>
                <span className="mono">{String(active.arguments_hash)}</span>
              </div>
              <div>
                <strong>Provenance</strong>
                <span className={`pill ${String(active.provenance_status)}`}>
                  {String(active.provenance_status)}
                </span>
              </div>
              <div>
                <strong>Latency</strong>
                <span>{String(active.latency_ms)} ms</span>
              </div>
              <div>
                <strong>Explanation</strong>
                <span>{String(active.explanation || "—")}</span>
              </div>
              <div>
                <strong>Redacted args</strong>
                <span className="mono" style={{ fontSize: "0.8rem" }}>
                  {JSON.stringify(active.arguments_redacted || {}, null, 0)}
                </span>
              </div>
              <div>
                <strong>Evidence count</strong>
                <span>
                  {Array.isArray(active.evidence) ? active.evidence.length : 0}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
