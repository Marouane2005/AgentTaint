"use client";

import { useEffect, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchDecisions, fetchHealth } from "@/lib/api";
import { PageHint } from "@/components/PageHint";

export default function GatewayPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchDecisions>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof fetchHealth>> | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
    fetchDecisions()
      .then((payload) => {
        setData(payload);
        if (payload.items[0]) {
          setSelected(String(payload.items[0].call_id));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const items = data?.items || [];
  const active = items.find((i) => String(i.call_id) === selected);

  return (
    <>
      <PageHint id="gateway" title="Security gateway">
        The gateway sits between the agent and its tools. This page shows its configuration and live
        status: which tools are high risk, which policy is loaded and whether the provenance
        registry and audit store are healthy.
      </PageHint>
      <div className="topbar">
        <div>
          <p className="eyebrow">Enforcement</p>
          <h1>Security Gateway</h1>
          <p>
            Intercepted MCP tool decisions from the audit store — argument hashes and redacted
            fields only. This page inspects decisions; it never weakens policy.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      <div className="panel">
        <div className="panel-head">
          <h2>Health checks</h2>
          <span className="panel-meta">{health ? health.status : "checking"}</span>
        </div>
        {!health ? (
          <div className="empty">Waiting for GET /api/v1/health.</div>
        ) : (
          <div className="status-grid">
            {(
              [
                ["Provenance registry", health.registry_ok],
                ["Audit store", health.audit_ok],
                ["Cedar policy engine", health.policy_ok],
              ] as const
            ).map(([label, ok]) => (
              <div className="status-row" key={label}>
                <span className="k">{label}</span>
                <span className="v">{ok ? "reachable" : "not confirmed"}</span>
              </div>
            ))}
            <div className="status-row">
              <span className="k">Auth</span>
              <span className="v mono">{health.auth_mode || "—"}</span>
            </div>
            <div className="status-row">
              <span className="k">Demo mode</span>
              <span className="v">{health.demo_mode ? "on" : "off"}</span>
            </div>
          </div>
        )}
      </div>
      {loading ? <div className="loading">Loading audit trail…</div> : null}

      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <h2>Decision timeline</h2>
            <span className="panel-meta">{items.length} records</span>
          </div>
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
                      className={`clickable ${selected === String(row.call_id) ? "selected" : ""}`}
                      aria-selected={selected === String(row.call_id)}
                      onClick={() => setSelected(String(row.call_id))}
                    >
                      <td>
                        <span className={`pill ${String(row.decision)}`}>
                          {String(row.decision)}
                        </span>
                      </td>
                      <td className="mono">{String(row.tool)}</td>
                      <td>
                        <span className={`pill ${String(row.risk_tier)}`}>
                          {String(row.risk_tier)}
                        </span>
                      </td>
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
          <div className="panel-head">
            <h2>Inspection</h2>
          </div>
          {!active ? (
            <div className="empty">Select a decision.</div>
          ) : (
            <div className="status-grid">
              <div className="status-row">
                <span className="k">Call ID</span>
                <span className="v mono" style={{ fontSize: "0.75rem" }}>
                  {String(active.call_id)}
                </span>
              </div>
              <div className="status-row">
                <span className="k">Decision</span>
                <span className="v">
                  <span className={`pill ${String(active.decision)}`}>
                    {String(active.decision)}
                  </span>
                </span>
              </div>
              <div className="status-row">
                <span className="k">Args hash</span>
                <span className="v mono" style={{ fontSize: "0.72rem" }}>
                  {String(active.arguments_hash)}
                </span>
              </div>
              <div className="status-row">
                <span className="k">Provenance</span>
                <span className="v">
                  <span className={`pill ${String(active.provenance_status)}`}>
                    {String(active.provenance_status)}
                  </span>
                </span>
              </div>
              <div className="status-row">
                <span className="k">Latency</span>
                <span className="v">{String(active.latency_ms)} ms</span>
              </div>
              <div className="status-row">
                <span className="k">Evidence</span>
                <span className="v">
                  {Array.isArray(active.evidence) ? active.evidence.length : 0}
                </span>
              </div>
              <div className="status-row">
                <span className="k">Explanation</span>
                <span className="v" style={{ textAlign: "left", maxWidth: "18rem" }}>
                  {String(active.explanation || "—")}
                </span>
              </div>
              <div>
                <div className="k" style={{ marginTop: "0.75rem" }}>
                  Redacted arguments
                </div>
                <div className="detail-block mono">
                  {JSON.stringify(active.arguments_redacted || {}, null, 2)}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
