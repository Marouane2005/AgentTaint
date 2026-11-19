"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchBenchmarks, runDemoScenario, type DemoRunResult } from "@/lib/api";
import { PageHint } from "@/components/PageHint";

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
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchBenchmarks>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reportIdx, setReportIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scenarioId, setScenarioId] = useState("");
  const [runResult, setRunResult] = useState<DemoRunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    fetchBenchmarks()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  async function executeSelected() {
    if (!scenarioId) return;
    setRunning(true);
    setRunError(null);
    try {
      setRunResult(await runDemoScenario(scenarioId));
    } catch (err) {
      setRunResult(null);
      const msg = err instanceof Error ? err.message : String(err);
      setRunError(msg.startsWith("429") ? "Rate limit reached. Wait a minute and try again." : msg);
    } finally {
      setRunning(false);
    }
  }

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
      <PageHint id="benchmarks" title="Benchmark lab">
        Results of the synthetic benchmark: how often attacks succeed with and without AgentTaint,
        and how many legitimate tasks still complete. Use it to judge the trade-off, keeping in mind
        the data is synthetic.
      </PageHint>
      <div className="topbar">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h1>Benchmark Lab</h1>
          <p>
            Measured synthetic results from <code>benchmarks/reports/</code>. Empty means not run —
            this UI never invents metrics or overclaims real-world effectiveness.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <div className="banner warn">{data?.disclaimer}</div>
      {loading ? <div className="loading">Loading measured reports…</div> : null}

      {data?.scenarios ? (
        <div className="panel">
          <div className="panel-head">
            <h2>Scenario catalogue</h2>
            <span className="panel-meta">
              {data.scenarios.catalog_count} runnable · input fixtures only
            </span>
          </div>
          <p className="panel-meta">{data.scenarios.note}</p>
          <div className="actions" style={{ margin: "0.8rem 0" }}>
            <label>
              Fixture
              <select
                className="control"
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
              >
                <option value="">Select a scenario</option>
                {data.scenarios.catalog.map((s) => (
                  <option key={s.scenario_id} value={s.scenario_id}>
                    {s.kind} · {s.family} · {s.scenario_id}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn" type="button" disabled={!scenarioId || running} onClick={executeSelected}>
              {running ? "Running…" : "Run through the gateway"}
            </button>
          </div>
          {runError ? <div className="banner danger">{runError}</div> : null}
          {runResult ? (
            <div className="status-grid">
              <div className="status-row">
                <span className="k">Without AgentTaint</span>
                <span className="v">{runResult.without_agenttaint.decision}</span>
              </div>
              <div className="status-row">
                <span className="k">With AgentTaint</span>
                <span className="v">
                  {runResult.with_agenttaint.decision} · {runResult.with_agenttaint.policy_id || "—"}
                </span>
              </div>
              <div className="status-row">
                <span className="k">Evidence</span>
                <span className="v mono">
                  {runResult.with_agenttaint.evidence_statuses.join(", ") || "—"}
                </span>
              </div>
            </div>
          ) : null}
          <div className="status-grid">
            {Object.entries(data.scenarios.counts || {}).map(([split, n]) => (
              <div className="status-row" key={split}>
                <span className="k">{split}</span>
                <span className="v mono">{n}</span>
              </div>
            ))}
          </div>
          {data.scenarios.message ? <div className="empty">{data.scenarios.message}</div> : null}
          {!data.scenarios.catalog_count ? (
            <div className="empty">No scenario files were found in this checkout.</div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Family</th>
                    <th>Split</th>
                    <th>Scenario</th>
                  </tr>
                </thead>
                <tbody>
                  {data.scenarios.catalog.map((s) => (
                    <tr key={s.scenario_id}>
                      <td>{s.kind}</td>
                      <td className="mono">{s.family}</td>
                      <td className="mono">{s.split}</td>
                      <td>
                        {s.description}{" "}
                        <span className="mono dim">{s.scenario_id}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-head">
          <h2>External benchmarks</h2>
          <span className="panel-meta">not evaluated here</span>
        </div>
        <p>
          AgentDojo and InjecAgent do not have a published attack-success figure in this demo. This
          page does not fill one in. The tables below are the synthetic suite only.
        </p>
      </div>

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
              <ul
                style={{
                  margin: 0,
                  paddingLeft: "1.1rem",
                  color: "var(--text-secondary)",
                }}
              >
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
