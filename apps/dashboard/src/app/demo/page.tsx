"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  fetchDemoScenarios,
  runDemoScenario,
  type DemoRunResult,
  type DemoScenario,
} from "@/lib/api";
import { PageHint } from "@/components/PageHint";
import { Skeleton } from "@/components/Skeleton";
import { TryIt } from "@/components/try/TryIt";

function outcome(r: DemoRunResult["without_agenttaint"], kind: string): string {
  if (kind === "attack") {
    return r.attack_success ? "attack succeeded" : "attack did not succeed";
  }
  return r.benign_completed ? "task completed" : "task not completed";
}

const SPOTLIGHT = [
  { id: "test-atk-direct-01", title: "Prompt injection in an email" },
  { id: "test-atk-summary-01", title: "Instructions hidden in summarized content" },
  { id: "test-atk-delegate-01", title: "Information transferred between agents" },
  { id: "test-ben-auth-01", title: "Legitimate request" },
  { id: "chal-atk-user-only-wrong-01", title: "Suspicious request" },
] as const;

function familyLabel(f: string) {
  return f.replace(/_/g, " ");
}

/**
 * Visitors replay synthetic scenarios through the real gateway and Cedar policy.
 * Tools are mocks: nothing is sent anywhere. Each run is added to the shared
 * demo session, so it shows up in Provenance and Audit.
 */
export default function DemoPage() {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [catalogState, setCatalogState] = useState<"loading" | "ready" | "error">("loading");
  const [results, setResults] = useState<DemoRunResult[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "attack" | "benign">("all");

  useEffect(() => {
    fetchDemoScenarios()
      .then((r) => {
        setScenarios(Array.isArray(r.scenarios) ? r.scenarios : []);
        setCatalogState("ready");
      })
      .catch((e) => {
        setCatalogState("error");
        setError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  const shown = useMemo(
    () => scenarios.filter((s) => filter === "all" || s.kind === filter),
    [scenarios, filter],
  );

  async function run(id: string) {
    setBusy(id);
    setError(null);
    try {
      const res = await runDemoScenario(id);
      setResults((prev) => [res, ...prev].slice(0, 12));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg.startsWith("429") ? "Rate limit reached. Wait a minute and try again." : msg);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="console">
      <PageHint id="demo" title="How to use this page">
        Start with &quot;Try your own text&quot;: pick an example or type an instruction and an email,
        then press Run. Below it you can replay benchmark scenarios, which include harder cases
        (summaries, paraphrases, several agents). Every run goes through the real AgentTaint
        gateway with mocked tools and shows up in Provenance and Audit.
      </PageHint>
      <div className="console-head">
        <div>
          <p className="eyebrow">Live demo · mock tools</p>
          <h1>Try your own text</h1>
        </div>
      </div>
      <TryIt compact />
      <div className="panel" style={{ marginTop: "1rem" }}>
        <div className="panel-head">
          <h2>Example fixtures</h2>
          <span className="panel-meta">results come from running them</span>
        </div>
        <p className="panel-meta">
          These are named inputs from the synthetic catalogue, including a case that the current
          policy holds for a person. The verdict is whatever the gateway returns for that run. The
          proposing side is a scripted pipeline with mock tools, not a language model.
        </p>
        <div className="actions">
          {SPOTLIGHT.map((item) => {
            const known = scenarios.some((s) => s.scenario_id === item.id);
            return (
              <button
                key={item.id}
                className="btn secondary"
                type="button"
                disabled={!known || busy !== null}
                onClick={() => run(item.id)}
              >
                {busy === item.id ? "Running…" : item.title}
              </button>
            );
          })}
        </div>
        {catalogState === "ready" &&
        SPOTLIGHT.some((item) => !scenarios.some((s) => s.scenario_id === item.id)) ? (
          <p className="panel-meta">A listed fixture is missing from this catalogue, so its button stays off.</p>
        ) : null}
      </div>
      <div className="console-head" style={{ marginTop: "2rem" }}>
        <div>
          <p className="eyebrow">Benchmark scenarios · synthetic</p>
          <h2 className="try-section-title">Or replay a scripted scenario</h2>
          <p className="sub">
            Each scenario is a scripted agent pipeline: it reads mock email, transforms the text
            (summaries, paraphrases, other agents) and finally tries{" "}
            <span className="mono">email.send</span>. We run it twice: once with no defense, once
            through the real AgentTaint gateway and Cedar policy. Nothing leaves this server: every
            tool is a mock.
          </p>
        </div>
        <div className="actions">
          <div className="seg" role="tablist" aria-label="Filter scenarios">
            {(["all", "attack", "benign"] as const).map((f) => (
              <button
                key={f}
                role="tab"
                aria-selected={filter === f}
                className={filter === f ? "btn" : "btn secondary"}
                onClick={() => setFilter(f)}
              >
                {f === "all" ? "All" : f === "attack" ? "Attacks" : "Benign"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}

      <div className="demo-grid">
        <section className="card">
          <header>
            <h2>Scenarios</h2>
            <span className="meta">
              {catalogState === "loading"
                ? "Loading scenarios…"
                : catalogState === "error"
                  ? "Unavailable"
                  : `${shown.length} available`}
            </span>
          </header>
          {catalogState === "loading" ? <Skeleton label="Loading scenarios" rows={4} /> : null}
          {catalogState === "ready" && !shown.length ? (
            <div className="empty">No scenarios match this filter.</div>
          ) : null}
          <ul className="scenario-list">
            {shown.map((s) => (
              <li key={s.scenario_id} className="scenario-item">
                <div>
                  <span className={`dec ${s.kind === "attack" ? "BLOCK" : "ALLOW"}`}>{s.kind}</span>{" "}
                  <span className="dim">{familyLabel(s.family)}</span>
                  {s.difficulty === "hard" ? <span className="dim"> · hard</span> : null}
                  <p>{s.description}</p>
                  <span className="mono dim small">{s.scenario_id}</span>
                </div>
                <button
                  className="btn"
                  disabled={busy !== null}
                  onClick={() => run(s.scenario_id)}
                  aria-label={`Run ${s.scenario_id}`}
                >
                  {busy === s.scenario_id ? "Running…" : "Run"}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <header>
            <h2>Results</h2>
            <span className="meta">newest first</span>
          </header>
          {!results.length ? <div className="empty">Pick a scenario and press Run.</div> : null}
          <ul className="result-list">
            {results.map((r) => (
              <li key={r.trace_id} className="result-item" data-testid="demo-result">
                <div className="ri-head">
                  <strong>{r.scenario.description}</strong>
                  <span className="mono dim small">{r.trace_id}</span>
                </div>
                <div className="ri-compare">
                  <div>
                    <span className="eyebrow">Without AgentTaint</span>
                    <div>
                      <span className={`dec ${r.without_agenttaint.decision}`}>
                        {r.without_agenttaint.decision}
                      </span>{" "}
                      <span className="dim">{outcome(r.without_agenttaint, r.scenario.kind)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="eyebrow">With AgentTaint</span>
                    <div>
                      <span className={`dec ${r.with_agenttaint.decision}`}>
                        {r.with_agenttaint.decision}
                      </span>{" "}
                      <span className="dim">{outcome(r.with_agenttaint, r.scenario.kind)}</span>
                    </div>
                  </div>
                </div>
                <div className="ri-meta mono small">
                  policy {r.with_agenttaint.policy_id || "—"} · evidence{" "}
                  {r.with_agenttaint.evidence_statuses.join(", ") || "—"} ·{" "}
                  {r.with_agenttaint.latency_ms} ms
                </div>
                <div className="ri-links">
                  <Link href={`/provenance?trace=${encodeURIComponent(r.trace_id)}`}>
                    View provenance
                  </Link>
                  <Link href="/audit">Audit log</Link>
                </div>
              </li>
            ))}
          </ul>
          <p className="sub small">
            CONFIRM means the call is held for a person. In this public demo approvals are locked;
            see <Link href="/confirmations">Confirmations</Link>.
          </p>
        </section>
      </div>
    </div>
  );
}
