"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarList,
  DECISION_COLORS,
  DestinationMap,
  Donut,
  Gauge,
  TimelineChart,
} from "@/components/charts";
import { DecisionTable } from "@/components/DecisionTable";
import { SessionBanner } from "@/components/SessionBanner";
import {
  clearSession,
  fetchAllDecisions,
  fetchGraph,
  fetchHealth,
  fetchOverview,
  seedDemo,
  type Decision,
} from "@/lib/api";
import {
  countBy,
  decisionTimeline,
  destinationFlows,
  provenanceCoverage,
  riskGauges,
  toolUsage,
  type SpanEdge,
  type SpanNode,
} from "@/lib/derive";
import { useDemoMode } from "@/lib/useDemoMode";
import { PageHint } from "@/components/PageHint";

const TIER_COLORS: Record<string, string> = {
  LOW: "#22d3ee",
  MEDIUM: "#f2b937",
  HIGH: "#ff5f6d",
};

export default function OverviewPage() {
  const demo = useDemoMode();
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof fetchOverview>> | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [edges, setEdges] = useState<SpanEdge[]>([]);
  const [spans, setSpans] = useState<SpanNode[]>([]);
  const [health, setHealth] = useState("checking…");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [o, h, d, g] = await Promise.all([
        fetchOverview(),
        fetchHealth(),
        fetchAllDecisions(),
        fetchGraph(),
      ]);
      setOverview(o);
      setHealth(h.status);
      setDecisions(d.items);
      setEdges(g.edges as SpanEdge[]);
      setSpans(g.nodes as SpanNode[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const timeline = useMemo(() => decisionTimeline(decisions), [decisions]);
  const gauges = useMemo(() => riskGauges(decisions, edges), [decisions, edges]);
  const flows = useMemo(() => destinationFlows(decisions), [decisions]);
  const tiers = useMemo(() => countBy(decisions, (d) => d.risk_tier), [decisions]);
  const policies = useMemo(() => countBy(decisions, (d) => d.policy_id || "—"), [decisions]);
  const counts = useMemo(() => countBy(decisions, (d) => d.decision), [decisions]);
  const tools = useMemo(() => toolUsage(decisions).slice(0, 6), [decisions]);
  const coverage = useMemo(() => provenanceCoverage(spans), [spans]);
  const suspicious = useMemo(
    () => decisions.filter((d) => d.decision === "BLOCK" || d.decision === "CONFIRM").slice(0, 6),
    [decisions],
  );
  const latencies = decisions.map((d) => Number(d.latency_ms || 0)).sort((a, b) => a - b);
  const p50 = latencies.length ? latencies[Math.floor(latencies.length / 2)] : 0;
  const graph = overview?.graph || {};

  const kpis = [
    {
      label: "Gateway decisions",
      value: decisions.length,
      tone: "cyan",
      hint: "audit store",
    },
    {
      label: "Blocked",
      value: counts.BLOCK || 0,
      tone: "block",
      hint: "BLOCK",
    },
    {
      label: "Awaiting human",
      value: counts.CONFIRM || 0,
      tone: "confirm",
      hint: "CONFIRM",
    },
    {
      label: "Allowed",
      value: counts.ALLOW || 0,
      tone: "allow",
      hint: "ALLOW",
    },
    {
      label: "Provenance spans",
      value: Number(graph.spans || 0),
      tone: "cyan",
      hint: `${graph.edges || 0} edges`,
    },
    {
      label: "Median latency",
      value: `${p50} ms`,
      tone: "cyan",
      hint: "policy + audit",
    },
  ];

  return (
    <div className="console">
      <PageHint id="overview" title="Security overview">
        A summary of every tool call the gateway has judged in this session: how many were allowed,
        held for approval (CONFIRM) or blocked, and which policies fired. Run a scenario or try your
        own text, then come back to see the totals change.
      </PageHint>
      <div className="console-head">
        <div>
          <p className="eyebrow">Investigative console</p>
          <h1>Security overview</h1>
          <p className="sub">
            Every number below is read from the audit store and provenance registry. The demo seed
            runs synthetic scenarios through the real SecurityGateway; it is not production
            telemetry.
          </p>
        </div>
        <div className="actions">
          <span className={`health ${health === "ok" ? "ok" : "err"}`}>API {health}</span>
          {demo ? (
            <Link className="btn" href="/demo">
              Run an attack scenario
            </Link>
          ) : (
            <>
              <button className="btn secondary" onClick={() => run(clearSession)} disabled={busy}>
                Clear session
              </button>
              <button className="btn" onClick={() => run(seedDemo)} disabled={busy}>
                {busy ? "Seeding…" : "Seed demo session"}
              </button>
            </>
          )}
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={overview?.session} />

      <div className="kpi-row">
        {kpis.map((k) => (
          <div key={k.label} className={`kpi ${k.tone}`}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
            <div className="kpi-hint">{k.hint}</div>
          </div>
        ))}
      </div>

      <div className="console-grid">
        <section className="card">
          <header>
            <h2>Most-used tools</h2>
            <span className="meta">from the audit store</span>
          </header>
          {!tools.length ? (
            <div className="empty">No tool calls in this session.</div>
          ) : (
            <ul className="plain-list">
              {tools.map((tool) => (
                <li key={tool.name}>
                  <span className="mono">{tool.name}</span>
                  <span className="meta">{tool.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <header>
            <h2>Provenance coverage</h2>
            <span className="meta">{coverage.total} spans</span>
          </header>
          {!coverage.total ? (
            <div className="empty">No spans yet. Coverage appears after a real run.</div>
          ) : (
            <ul className="plain-list">
              <li>
                <span>KNOWN</span>
                <span>{coverage.known}</span>
              </li>
              <li>
                <span>INFERRED</span>
                <span>{coverage.inferred}</span>
              </li>
              <li>
                <span>UNKNOWN</span>
                <span>{coverage.unknown}</span>
              </li>
              <li>
                <span>PARTIAL</span>
                <span>{coverage.partial}</span>
              </li>
            </ul>
          )}
        </section>
        <section className="card">
          <header>
            <h2>Suspicious activity</h2>
            <span className="meta">BLOCK and CONFIRM</span>
          </header>
          {!suspicious.length ? (
            <div className="empty">No blocked or held calls in the loaded audit page.</div>
          ) : (
            <ul className="plain-list">
              {suspicious.map((row) => (
                <li key={row.call_id}>
                  <span className={`dec ${row.decision}`}>{row.decision}</span>
                  <span className="mono">{row.tool}</span>
                  <span className="dim">{row.policy_id || "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card span-2">
          <header>
            <h2>Decision timeline</h2>
            <div className="legend-inline">
              {(["ALLOW", "CONFIRM", "BLOCK"] as const).map((k) => (
                <span key={k}>
                  <i style={{ background: DECISION_COLORS[k] }} />
                  {k}
                </span>
              ))}
            </div>
          </header>
          <TimelineChart bins={timeline.bins} widthMs={timeline.widthMs} />
        </section>
        <section className="card">
          <header>
            <h2>Risk gauges</h2>
          </header>
          <div className="gauge-grid">
            <Gauge
              value={gauges.blockRate}
              label="Block rate"
              hint="BLOCK / decisions"
              color="#ff5f6d"
            />
            <Gauge
              value={gauges.reviewLoad}
              label="Human review load"
              hint="CONFIRM / decisions"
              color="#f2b937"
            />
            <Gauge
              value={gauges.unverifiedProvenance}
              label="Unverified provenance"
              hint="decisions not KNOWN"
              color="#a78bfa"
            />
            <Gauge
              value={gauges.inferredLineage}
              label="Inferred lineage"
              hint="inferred / all edges"
              color="#22d3ee"
            />
          </div>
        </section>

        <section className="card span-2">
          <header>
            <h2>Destination map</h2>
            <span className="meta">agents → tools → destination class · redacted addresses</span>
          </header>
          <DestinationMap {...flows} />
        </section>
        <section className="card">
          <header>
            <h2>Risk tiers</h2>
          </header>
          <Donut data={tiers} colors={TIER_COLORS} />
          <header style={{ marginTop: "1rem" }}>
            <h2>Top policies</h2>
          </header>
          <BarList data={policies} />
        </section>

        <section className="card span-3">
          <header>
            <h2>Recent decisions</h2>
            <span className="meta">latest 12 of {decisions.length}</span>
          </header>
          <DecisionTable rows={decisions.slice(0, 12)} />
        </section>
      </div>
    </div>
  );
}
