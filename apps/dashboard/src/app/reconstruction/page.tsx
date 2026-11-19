"use client";

import { useEffect, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchReconstruction } from "@/lib/api";
import { PageHint } from "@/components/PageHint";

function Meter({
  label,
  value,
  kind,
}: {
  label: string;
  value: number;
  kind: "lexical" | "semantic" | "structural";
}) {
  const width = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="meter" title={`${label}: ${value.toFixed(3)}`}>
      <span className="panel-meta" style={{ width: "4.5rem" }}>
        {label}
      </span>
      <div className="meter-track">
        <div className={`meter-fill ${kind}`} style={{ width: `${width}%` }} />
      </div>
      <span className="meter-val mono">{value.toFixed(3)}</span>
    </div>
  );
}

export default function ReconstructionPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchReconstruction>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    fetchReconstruction()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const evidence = data?.evidence || [];
  const active = evidence[selected];

  return (
    <>
      <PageHint id="reconstruction" title="Reconstruction inspector">
        When an agent does not declare where a value came from, AgentTaint compares it with
        everything the agent read and scores possible sources. These matches are evidence for
        scrutiny, not proof of causation.
      </PageHint>
      <div className="topbar">
        <div>
          <p className="eyebrow">Scrutiny</p>
          <h1>Reconstruction Inspector</h1>
          <p>
            Lexical, structural, and semantic signals attached to authority arguments. INFERRED
            evidence is a scrutiny signal — never verified lineage.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      <div className="banner warn">{data?.disclaimer}</div>
      {loading ? <div className="loading">Loading reconstruction evidence…</div> : null}

      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <h2>Evidence ledger</h2>
            <span className="panel-meta mono">source={data?.source || "—"}</span>
          </div>
          {data?.empty ? (
            <div className="empty">{data.message}</div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Argument</th>
                    <th>Status</th>
                    <th>Type</th>
                    <th>Channels</th>
                    <th>Explicit</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.map((row, idx) => (
                    <tr
                      key={`${row.argument_name}-${idx}`}
                      className={`clickable ${selected === idx ? "selected" : ""}`}
                      aria-selected={selected === idx}
                      onClick={() => setSelected(idx)}
                    >
                      <td className="mono">{String(row.argument_name)}</td>
                      <td>
                        <span className={`pill ${String(row.provenance_status)}`}>
                          {String(row.provenance_status)}
                        </span>
                      </td>
                      <td>
                        <span className={`pill ${String(row.evidence_type)}`}>
                          {String(row.evidence_type)}
                        </span>
                      </td>
                      <td className="mono" style={{ fontSize: "0.78rem" }}>
                        L {Number(row.lexical_score || 0).toFixed(2)} · S{" "}
                        {Number(row.semantic_score || 0).toFixed(2)} · Str{" "}
                        {row.structural_match ? "yes" : "no"}
                      </td>
                      <td>{row.explicit_lineage ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Channel strength</h2>
          </div>
          {!active ? (
            <div className="empty">Select an evidence row.</div>
          ) : (
            <>
              <p style={{ marginTop: 0 }}>
                Argument <span className="mono">{String(active.argument_name)}</span> ·{" "}
                <span className={`pill ${String(active.provenance_status)}`}>
                  {String(active.provenance_status)}
                </span>
              </p>
              <div style={{ display: "grid", gap: "0.7rem", marginTop: "0.85rem" }}>
                <Meter label="Lexical" value={Number(active.lexical_score || 0)} kind="lexical" />
                <Meter
                  label="Semantic"
                  value={Number(active.semantic_score || 0)}
                  kind="semantic"
                />
                <Meter
                  label="Structural"
                  value={active.structural_match ? 1 : 0}
                  kind="structural"
                />
              </div>
              <div className="status-grid" style={{ marginTop: "1rem" }}>
                <div className="status-row">
                  <span className="k">Evidence type</span>
                  <span className="v">
                    <span className={`pill ${String(active.evidence_type)}`}>
                      {String(active.evidence_type)}
                    </span>
                  </span>
                </div>
                <div className="status-row">
                  <span className="k">Explicit lineage</span>
                  <span className="v">{active.explicit_lineage ? "yes" : "no"}</span>
                </div>
                <div className="status-row">
                  <span className="k">Matched sources</span>
                  <span className="v mono" style={{ fontSize: "0.75rem" }}>
                    {Array.isArray(active.matched_source_ids) && active.matched_source_ids.length
                      ? active.matched_source_ids
                          .map((id: string) => `${String(id).slice(0, 8)}…`)
                          .join(", ")
                      : "— (missing / unknown)"}
                  </span>
                </div>
              </div>
              <p className="panel-meta">
                Lexical is text overlap. Structural is an exact value match. Semantic is embedding
                similarity; a zero means this row has no semantic support, not that a model proved
                the value is clean.
                {active.explicit_lineage
                  ? " Explicit lineage was declared by instrumentation."
                  : " This row is not explicit lineage."}{" "}
                {String(active.evidence_type) === "INFERRED"
                  ? "INFERRED is a scrutiny signal, not a proven origin."
                  : `Recorded evidence type: ${String(active.evidence_type)}.`}
              </p>
              {!active.explicit_lineage ? (
                <div className="banner warn" style={{ marginTop: "1rem", marginBottom: 0 }}>
                  No explicit lineage for this match. Treat as scrutiny only.
                </div>
              ) : (
                <div className="banner" style={{ marginTop: "1rem", marginBottom: 0 }}>
                  Explicit lineage is what the caller declared. It is not a reconstruction guess.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
