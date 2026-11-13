"use client";

import { useEffect, useState } from "react";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchReconstruction } from "@/lib/api";

export default function ReconstructionPage() {
  const [data, setData] = useState<Awaited<
    ReturnType<typeof fetchReconstruction>
  > | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReconstruction()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const evidence = data?.evidence || [];

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Reconstruction Inspector</h1>
          <p>
            Lexical, structural, and semantic signals attached to authority arguments.
            INFERRED never appears as verified lineage.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      <div className="banner warn">{data?.disclaimer}</div>
      <div className="panel">
        <h2>
          Evidence{" "}
          <span className="mono" style={{ color: "var(--muted)", fontWeight: 400 }}>
            source={data?.source || "—"}
          </span>
        </h2>
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
                  <th>Lexical</th>
                  <th>Semantic</th>
                  <th>Structural</th>
                  <th>Explicit</th>
                  <th>Matched sources</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((row, idx) => (
                  <tr key={`${row.argument_name}-${idx}`}>
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
                    <td className="mono">
                      {Number(row.lexical_score || 0).toFixed(3)}
                    </td>
                    <td className="mono">
                      {Number(row.semantic_score || 0).toFixed(3)}
                    </td>
                    <td>{row.structural_match ? "yes" : "no"}</td>
                    <td>{row.explicit_lineage ? "yes" : "no"}</td>
                    <td className="mono" style={{ fontSize: "0.8rem" }}>
                      {Array.isArray(row.matched_source_ids)
                        ? row.matched_source_ids
                            .map((id: string) => `${String(id).slice(0, 8)}…`)
                            .join(", ") || "—"
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
