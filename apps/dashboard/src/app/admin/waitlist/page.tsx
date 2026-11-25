"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { SiteHeader } from "@/components/site/SiteHeader";
import { downloadWaitlistCsv, fetchWaitlist, type WaitlistEntry } from "@/lib/api";

/**
 * Operator view of waitlist signups. The admin token is typed by the
 * operator, kept in memory for this tab only and sent as X-AgentTaint-Admin.
 */
export default function WaitlistAdminPage() {
  const [token, setToken] = useState("");
  const [entries, setEntries] = useState<WaitlistEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(e?: FormEvent) {
    e?.preventDefault();
    setError(null);
    try {
      const res = await fetchWaitlist(token);
      setEntries(res.entries);
    } catch (err) {
      setEntries(null);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function exportCsv() {
    try {
      const csv = await downloadWaitlistCsv(token);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "agenttaint-waitlist.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="site">
      <SiteHeader />
      <main className="doc">
        <p className="eyebrow">Operator only</p>
        <h1>Waitlist signups</h1>
        {entries === null ? (
          <form className="card approver-gate" onSubmit={load}>
            <p className="sub">
              Enter the admin token (<span className="mono">AGENTTAINT_ADMIN_TOKEN</span>). It is
              kept in memory for this tab only.
            </p>
            <input
              type="password"
              autoComplete="off"
              aria-label="Admin token"
              placeholder="Admin token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <button className="btn" type="submit" disabled={!token}>
              Show signups
            </button>
          </form>
        ) : (
          <section className="card">
            <header>
              <h2>{entries.length} signups</h2>
              <span className="actions">
                <button className="btn secondary" onClick={() => load()}>
                  Refresh
                </button>
                <button className="btn secondary" onClick={exportCsv}>
                  Export CSV
                </button>
                <button
                  className="btn secondary"
                  onClick={() => {
                    setToken("");
                    setEntries(null);
                  }}
                >
                  Lock
                </button>
              </span>
            </header>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Plan</th>
                    <th>Source</th>
                    <th>Joined (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.email}>
                      <td className="mono">{e.email}</td>
                      <td>{e.plan}</td>
                      <td>{e.source}</td>
                      <td className="mono">{e.created_at.replace("T", " ").slice(0, 19)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {error ? <div className="banner danger">{error}</div> : null}
      </main>
    </div>
  );
}
