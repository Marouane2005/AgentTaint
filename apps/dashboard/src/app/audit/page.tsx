"use client";

import { useEffect, useState } from "react";
import { DecisionTable } from "@/components/DecisionTable";
import { fetchDecisions, type Decision } from "@/lib/api";
import { formatUtcTime, parseTs } from "@/lib/derive";
import { PageHint } from "@/components/PageHint";

const PAGE = 25;

export default function AuditPage() {
  const [rows, setRows] = useState<Decision[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState("ALL");
  const [tier, setTier] = useState("ALL");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"created_at" | "tool" | "decision" | "risk_tier">("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Decision | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setLoading(true);
      fetchDecisions({
        limit: PAGE,
        offset,
        decision: decision === "ALL" ? undefined : decision,
        risk_tier: tier === "ALL" ? undefined : tier,
        q: q.trim() || undefined,
        sort,
        order,
      })
        .then((d) => {
          const items = d.items as Decision[];
          setRows(items);
          setTotal(typeof d.total === "number" ? d.total : items.length);
          setSelected((current) =>
            current && items.some((row) => row.call_id === current.call_id)
              ? current
              : items.find((row) => row.decision === "BLOCK") || items[0] || null,
          );
          setError(null);
        })
        .catch((err) => setError(err instanceof Error ? err.message : String(err)))
        .finally(() => setLoading(false));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [decision, tier, q, offset, sort, order]);

  return (
    <div className="console">
      <PageHint id="audit" title="Decisions and audit log">
        Every row is one tool call the agent tried. ALLOW ran, CONFIRM was held for a person, BLOCK
        never reached the tool. Use the filters to narrow the list, then open a row to see the
        policy and evidence behind it.
      </PageHint>
      <div className="console-head">
        <div>
          <p className="eyebrow">Audit trail</p>
          <h1>Decisions &amp; audit log</h1>
          <p className="sub">
            Append-only gateway decisions with redacted arguments, argument hashes, provenance
            evidence and the policy that fired.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <div className="filters">
        <label>
          Decision
          <select
            value={decision}
            onChange={(e) => {
              setDecision(e.target.value);
              setOffset(0);
            }}
          >
            {["ALL", "ALLOW", "CONFIRM", "BLOCK"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Risk tier
          <select
            value={tier}
            onChange={(e) => {
              setTier(e.target.value);
              setOffset(0);
            }}
          >
            {["ALL", "LOW", "MEDIUM", "HIGH"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="grow">
          Search
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            placeholder="tool, agent, policy or call id"
          />
        </label>
        <label>
          Sort
          <select
            value={`${sort}:${order}`}
            onChange={(e) => {
              const [nextSort, nextOrder] = e.target.value.split(":") as [
                typeof sort,
                typeof order,
              ];
              setSort(nextSort);
              setOrder(nextOrder);
              setOffset(0);
            }}
          >
            <option value="created_at:desc">Newest</option>
            <option value="created_at:asc">Oldest</option>
            <option value="tool:asc">Tool</option>
            <option value="decision:asc">Decision</option>
            <option value="risk_tier:desc">Risk</option>
          </select>
        </label>
        <span className="meta">
          {loading ? "Loading…" : `${rows.length} on this page · ${total} match`}
        </span>
      </div>
      <div className="actions" style={{ marginBottom: "0.8rem" }}>
        <button
          className="btn secondary"
          type="button"
          disabled={offset === 0 || loading}
          onClick={() => setOffset((n) => Math.max(0, n - PAGE))}
        >
          Previous
        </button>
        <button
          className="btn secondary"
          type="button"
          disabled={loading || offset + rows.length >= total}
          onClick={() => setOffset((n) => n + PAGE)}
        >
          Next
        </button>
      </div>
      {!loading && !rows.length ? (
        <div className="empty">No audit records match these filters.</div>
      ) : null}
      <div className="audit-grid">
        <section className="card">
          <DecisionTable rows={rows} onSelect={setSelected} selectedId={selected?.call_id} />
        </section>
        <section className="card audit-detail" aria-label="Decision detail">
          {selected ? (
            <>
              <header>
                <h2 className="mono">{selected.tool}</h2>
                <span className={`dec ${selected.decision}`}>{selected.decision}</span>
              </header>
              <dl>
                <dt>Call id</dt>
                <dd className="mono small">{selected.call_id}</dd>
                <dt>Time</dt>
                <dd className="mono">{formatUtcTime(parseTs(selected.created_at))} UTC</dd>
                <dt>Agent</dt>
                <dd className="mono">{selected.agent_id || "—"}</dd>
                <dt>Risk / provenance</dt>
                <dd>
                  {selected.risk_tier} · {selected.provenance_status}
                </dd>
                <dt>Policy</dt>
                <dd className="mono">{selected.policy_id || "—"}</dd>
                <dt>Explanation</dt>
                <dd>{selected.explanation}</dd>
                <dt>Arguments (redacted)</dt>
                <dd>
                  <pre>{JSON.stringify(selected.arguments_redacted || {}, null, 2)}</pre>
                </dd>
                <dt>Arguments hash</dt>
                <dd className="mono small">{selected.arguments_hash}</dd>
                <dt>Evidence</dt>
                <dd>
                  {(selected.evidence || []).length ? (
                    <table className="mini">
                      <thead>
                        <tr>
                          <th>arg</th>
                          <th>type</th>
                          <th>status</th>
                          <th>lex</th>
                          <th>sem</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selected.evidence || []).map((e, i) => (
                          <tr key={i}>
                            <td className="mono">{String(e.argument_name)}</td>
                            <td>{String(e.evidence_type)}</td>
                            <td>{String(e.provenance_status)}</td>
                            <td>{Number(e.lexical_score ?? 0).toFixed(2)}</td>
                            <td>{Number(e.semantic_score ?? 0).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    "—"
                  )}
                </dd>
              </dl>
            </>
          ) : (
            <div className="empty">Select a decision.</div>
          )}
        </section>
      </div>
    </div>
  );
}
