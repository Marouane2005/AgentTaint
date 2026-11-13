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

function BarChart({
  rows,
  metric,
  kind,
}: {
  rows: [string, Metrics][];
  metric: keyof Metrics;
  kind: "asr" | "utility" | "f1";
}) {
  return (
    <div className="bar-chart">
      {rows.map(([name, m]) => {
        const raw = m[metric];
        const val = typeof raw === "number" ? raw : 0;
        const width = Math.max(0, Math.min(100, val * 100));
        return (
          <div className="bar-row" key={`${name}-${String(metric)}`}>
            <div className="name" title={name}>
              {name}
            </div>
            <div className="bar-track">
              <div className={`bar-fill ${kind}`} style={{ width: `${width}%` }} />
            </div>
            <div className="bar-val mono">{fmt(typeof raw === "number" ? raw : null)}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function BenchmarksPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchBenchmarks>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [reportIdx, setReportIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBenchmarks()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
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
          <p className="eyebrow">Evaluation</p>
          <h1>Benchmark Lab</h1>
          <p>
            Measured synthetic results from <code>benchmarks/reports/</code>. Empty
            means not run — this UI never invents metrics or overclaims real-world
            effectiveness.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <div className="banner warn">{data?.disclaimer}</div>
      {loading ? <div className="loading">Loading measured reports…</div> : null}

      {!data?.available ? (
        <div className="panel">
          <div className="empty">{data?.message || "No reports available."}</div>
        </div>
      ) : (
        <>
          <div className="panel">
            <div className="panel-head">
              <h2>Measured report</h2>
              <span className="panel-meta">on-disk artifacts only</span>
            </div>
            <label
              style={{
                display: "flex",
                gap: "0.75rem",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <span className="panel-meta">Select report</span>
              <select
                className="control"
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
              <div className="status-grid" style={{ marginTop: "0.85rem" }}>
                <div className="status-row">
                  <span className="k">Dataset</span>
                  <span className="v mono">{String(report.dataset_version)}</span>
                </div>
                <div className="status-row">
                  <span className="k">Seed</span>
                  <span className="v mono">{String(report.seed)}</span>
                </div>
                <div className="status-row">
                  <span className="k">Backend</span>
                  <span className="v mono">{String(report.semantic_backend)}</span>
                </div>
              </div>
            ) : null}
          </div>

          <div className="three-col">
            <div className="panel">
              <div className="panel-head">
                <h2>ASR (lower better)</h2>
              </div>
              <BarChart rows={rows} metric="asr" kind="asr" />
            </div>
            <div className="panel">
              <div className="panel-head">
                <h2>Utility</h2>
              </div>
              <BarChart rows={rows} metric="utility" kind="utility" />
            </div>
            <div className="panel">
              <div className="panel-head">
                <h2>Provenance F1</h2>
              </div>
              <BarChart rows={rows} metric="provenance_f1" kind="f1" />
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Baselines table</h2>
            </div>
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
                      <td className="mono">{fmt(m.asr)}</td>
                      <td className="mono">{fmt(m.utility)}</td>
                      <td className="mono">{fmt(m.fpr_block)}</td>
                      <td className="mono">{fmt(m.provenance_f1)}</td>
                      <td className="mono">{fmt(m.latency_ms_median)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Ablations</h2>
            </div>
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
                        <td className="mono">{fmt(m.asr)}</td>
                        <td className="mono">{fmt(m.utility)}</td>
                        <td className="mono">{fmt(m.provenance_f1)}</td>
                        <td className="mono">{fmt(m.latency_ms_median)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {Array.isArray(report?.limitations) && report.limitations.length ? (
            <div className="panel">
              <div className="panel-head">
                <h2>Recorded limitations</h2>
              </div>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--text-secondary)" }}>
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
