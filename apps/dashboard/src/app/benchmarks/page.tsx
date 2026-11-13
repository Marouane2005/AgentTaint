"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchBenchmarks } from "@/lib/api";

type Metrics = {
  asr?: number | null;
  utility?: number | null;
  provenance_f1?: number | null;
  latency_ms_median?: number | null;
  fpr_block?: number | null;
  n_scenarios?: number;
};

function fmt(v: number | null | undefined) {
  if (v === null || v === undefined) return "n/a";
  return v.toFixed(3);
}

export default function BenchmarksPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchBenchmarks>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [reportIdx, setReportIdx] = useState(0);

  useEffect(() => {
    fetchBenchmarks()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const report = data?.reports?.[reportIdx];
  const rows = useMemo(() => {
    const per = (report?.per_defense || {}) as Record<string, Metrics>;
    return Object.entries(per).sort(([a], [b]) => a.localeCompare(b));
  }, [report]);
  const ablations = useMemo(() => {
    const per = (report?.per_ablation || {}) as Record<string, Metrics>;
    return Object.entries(per).sort(([a], [b]) => a.localeCompare(b));
  }, [report]);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Benchmark Lab</h1>
          <p>
            Measured synthetic results from <code>benchmarks/reports/</code>. Empty
            means not run — this UI never invents metrics.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <div className="banner warn">{data?.disclaimer}</div>
      {!data?.available ? (
        <div className="panel">
          <div className="empty">{data?.message || "No reports available."}</div>
        </div>
      ) : (
        <>
          <div className="panel">
            <h2>Report</h2>
            <label style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              <span>Select measured report</span>
              <select
                value={reportIdx}
                onChange={(e) => setReportIdx(Number(e.target.value))}
              >
                {(data.reports || []).map((r, idx) => (
                  <option key={String(r.report_id)} value={idx}>
                    {String(r.path)} · {String(r.semantic_backend || "backend?")} ·{" "}
                    {String(r.dataset_version)}
                  </option>
                ))}
              </select>
            </label>
            {report ? (
              <div className="legend" style={{ marginTop: "0.85rem" }}>
                <div>
                  <strong>Dataset</strong>
                  <span className="mono">{String(report.dataset_version)}</span>
                </div>
                <div>
                  <strong>Seed</strong>
                  <span className="mono">{String(report.seed)}</span>
                </div>
                <div>
                  <strong>Backend</strong>
                  <span className="mono">{String(report.semantic_backend)}</span>
                </div>
              </div>
            ) : null}
          </div>

          <div className="panel">
            <h2>Baselines</h2>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Config</th>
                    <th>n</th>
                    <th>ASR</th>
                    <th>Utility</th>
                    <th>FPR_block</th>
                    <th>Prov F1</th>
                    <th>lat_med_ms</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([name, m]) => (
                    <tr key={name}>
                      <td className="mono">{name}</td>
                      <td>{m.n_scenarios ?? "—"}</td>
                      <td>{fmt(m.asr)}</td>
                      <td>{fmt(m.utility)}</td>
                      <td>{fmt(m.fpr_block)}</td>
                      <td>{fmt(m.provenance_f1)}</td>
                      <td>{fmt(m.latency_ms_median)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Ablations</h2>
            {!ablations.length ? (
              <div className="empty">No ablation table in this report.</div>
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Ablation</th>
                      <th>ASR</th>
                      <th>Utility</th>
                      <th>Prov F1</th>
                      <th>lat_med_ms</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ablations.map(([name, m]) => (
                      <tr key={name}>
                        <td className="mono">{name}</td>
                        <td>{fmt(m.asr)}</td>
                        <td>{fmt(m.utility)}</td>
                        <td>{fmt(m.provenance_f1)}</td>
                        <td>{fmt(m.latency_ms_median)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {Array.isArray(report?.limitations) && report.limitations.length ? (
            <div className="panel">
              <h2>Recorded limitations</h2>
              <ul>
                {(report.limitations as string[]).slice(0, 8).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
