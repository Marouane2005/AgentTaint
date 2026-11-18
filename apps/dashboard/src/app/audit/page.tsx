"use client";

import { useEffect, useMemo, useState } from "react";
import { DecisionTable } from "@/components/DecisionTable";
import { fetchAllDecisions, type Decision } from "@/lib/api";
import { formatUtcTime, parseTs } from "@/lib/derive";

export default function AuditPage() {
  const [rows, setRows] = useState<Decision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState("ALL");
  const [tier, setTier] = useState("ALL");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Decision | null>(null);

  useEffect(() => {
    fetchAllDecisions()
      .then((d) => {
        setRows(d.items);
        setSelected(d.items.find((r) => r.decision === "BLOCK") || d.items[0] || null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (decision === "ALL" || r.decision === decision) &&
          (tier === "ALL" || r.risk_tier === tier) &&
          (!q ||
            `${r.tool} ${r.agent_id} ${r.policy_id} ${r.call_id}`.toLowerCase().includes(q.toLowerCase())),
      ),
    [rows, decision, tier, q],
  );

  return (
    <div className="console">
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
          <select value={decision} onChange={(e) => setDecision(e.target.value)}>
            {["ALL", "ALLOW", "CONFIRM", "BLOCK"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Risk tier
          <select value={tier} onChange={(e) => setTier(e.target.value)}>
            {["ALL", "LOW", "MEDIUM", "HIGH"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="grow">
          Search
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="tool, agent, policy or call id"
          />
        </label>
        <span className="meta">
          {filtered.length} of {rows.length}
        </span>
      </div>
      <div className="audit-grid">
        <section className="card">
          <DecisionTable rows={filtered} onSelect={setSelected} selectedId={selected?.call_id} />
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
