"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { decideConfirmation, fetchConfirmations, type PendingConfirmation } from "@/lib/api";
import { formatUtcTime, parseTs } from "@/lib/derive";
import { useDemoMode } from "@/lib/useDemoMode";
import { PageHint } from "@/components/PageHint";
import { StatePanel } from "@/components/StatePanel";
import { friendlyError } from "@/lib/errors";

const POLL_MS = 10_000;

/**
 * Human-only approval screen. The approver token is typed by a person and kept
 * in memory for this tab only. Agents never receive it: the MCP proxy exposes no
 * approval tool, and the API rejects the dashboard read token for approvals.
 */
export default function ConfirmationsPage() {
  const demo = useDemoMode();
  const [token, setToken] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [items, setItems] = useState<PendingConfirmation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [issued, setIssued] = useState<{ id: string; tool: string; token: string } | null>(null);

  async function load(t: string) {
    const res = await fetchConfirmations(t);
    setItems(res.pending);
  }

  // Keep the queue fresh while unlocked; a failed poll shows a retryable error.
  useEffect(() => {
    if (!unlocked) return;
    const timer = setInterval(() => {
      load(token).catch((err) => setError(friendlyError(err)));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [unlocked, token]);

  async function onUnlock(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await load(token);
      setUnlocked(true);
    } catch (err) {
      setUnlocked(false);
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  async function decide(id: string, action: "approve" | "deny") {
    setBusy(id);
    setError(null);
    try {
      const rec = await decideConfirmation(token, id, action);
      setLog((l) => [`${rec.status}: ${rec.tool} (${id.slice(0, 8)}…)`, ...l]);
      if (action === "approve" && rec.approval_token) {
        setIssued({ id, tool: rec.tool, token: rec.approval_token });
      }
      await load(token);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  function retry() {
    load(token)
      .then(() => setError(null))
      .catch((e) => setError(friendlyError(e)));
  }

  function lock() {
    setToken("");
    setUnlocked(false);
    setItems([]);
    setIssued(null);
  }

  return (
    <div className="console">
      <PageHint id="confirmations" title="Pending confirmations">
        Calls that policy held for a human decision appear here. In the public demo approving is
        switched off; an operator approves or denies with a separate approver
        token or the CLI.
      </PageHint>
      <div className="console-head">
        <div>
          <p className="eyebrow">Human approval channel</p>
          <h1>Pending confirmations</h1>
          <p className="sub">
            CONFIRM decisions wait here for a person. Approval is bound to the exact tool, arguments
            hash and agent, single-use, and expires. Agents cannot reach this screen: the MCP proxy
            has no approval tool and the API requires a separate approver token.
          </p>
        </div>
        {unlocked ? (
          <div className="actions">
            <button className="btn secondary" onClick={() => load(token)}>
              Refresh
            </button>
            <button className="btn secondary" onClick={lock}>
              Lock
            </button>
          </div>
        ) : null}
      </div>
      {error ? (
        <StatePanel
          kind="error"
          title="Something went wrong"
          onRetry={unlocked ? retry : undefined}
        >
          {error}
        </StatePanel>
      ) : null}
      {issued ? (
        <div className="banner ok" role="status">
          <strong>Approved {issued.tool}.</strong> Give this single-use token to the agent with
          the confirmation id; it is shown once and cannot be read back.
          <pre className="mono">{`_agenttaint: {"confirmation_id": "${issued.id}", "approval_token": "${issued.token}"}`}</pre>
          <button className="btn secondary" type="button" onClick={() => setIssued(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      {demo ? (
        <div className="card approver-gate" role="status">
          <h2>Approvals are locked in the public demo</h2>
          <p className="sub">
            Visitors can trigger CONFIRM decisions but nobody can approve them here: the demo server
            refuses every approval request, whatever token is sent. A person
            approves held calls with a separate approver token on this screen, or with{" "}
            <span className="mono">agenttaint approve</span> from a terminal the agent cannot reach.
          </p>
        </div>
      ) : !unlocked ? (
        <form className="card approver-gate" onSubmit={onUnlock}>
          <h2>Approver sign-in</h2>
          <p className="sub">
            Enter the approver token (<span className="mono">AGENTTAINT_APPROVER_TOKEN</span>). It
            is held in memory for this tab only and never stored or bundled.
          </p>
          <input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Approver token"
            aria-label="Approver token"
          />
          <button className="btn" type="submit" disabled={!token || loading}>
            {loading ? "Checking…" : "Unlock approvals"}
          </button>
        </form>
      ) : (
        <div className="confirm-grid">
          <section className="card">
            <header>
              <h2>Queue</h2>
              <span className="meta">{items.length} pending</span>
            </header>
            {!items.length ? (
              <StatePanel kind="empty">
                Nothing waiting. When an agent makes a high-risk call the policy cannot clear, it
                shows up here. Refreshes every 10 seconds.
              </StatePanel>
            ) : null}
            <ul className="confirm-list">
              {items.map((c) => (
                <li key={c.confirmation_id} className="confirm-item">
                  <div className="ci-top">
                    <span className={`tier ${c.risk_tier}`}>{c.risk_tier}</span>
                    <strong className="mono">{c.tool}</strong>
                    <span className="dim mono">agent {c.agent_id}</span>
                    <span className="dim mono">
                      expires {formatUtcTime(parseTs(c.expires_at))} UTC
                    </span>
                  </div>
                  <div className="ci-policy mono">{c.policy_id || "—"}</div>
                  <p className="ci-expl">{c.explanation}</p>
                  <pre>{JSON.stringify(c.arguments_redacted || {}, null, 2)}</pre>
                  <div className="ci-hash mono">args sha256 {c.arguments_hash.slice(0, 24)}…</div>
                  <div className="ci-actions">
                    <button
                      className="btn deny"
                      disabled={busy === c.confirmation_id}
                      onClick={() => decide(c.confirmation_id, "deny")}
                    >
                      Deny
                    </button>
                    <button
                      className="btn approve"
                      disabled={busy === c.confirmation_id}
                      onClick={() => decide(c.confirmation_id, "approve")}
                    >
                      Approve once
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
          <section className="card">
            <header>
              <h2>This session</h2>
            </header>
            {!log.length ? <div className="empty">No decisions taken yet.</div> : null}
            <ul className="confirm-log mono">
              {log.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
