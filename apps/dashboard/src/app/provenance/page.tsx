"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageHint } from "@/components/PageHint";
import { ProvenanceFlow } from "@/components/ProvenanceFlow";
import { Skeleton } from "@/components/Skeleton";
import {
  fetchAllDecisions,
  fetchAncestors,
  fetchGraph,
  fetchTraces,
  type Decision,
  type SessionInfo,
  type Trace,
} from "@/lib/api";
import {
  buildTraceGraph,
  formatUtcTime,
  traceTimeline,
  type SpanEdge,
  type SpanNode,
} from "@/lib/derive";

const ALL = "__all__";

function mergeTraces(traces: Trace[]): Trace {
  return {
    trace_id: ALL,
    label: "All traces",
    kind: "mixed",
    family: "all",
    source: "session",
    span_ids: traces.flatMap((t) => t.span_ids),
    call_ids: traces.flatMap((t) => t.call_ids),
    calls: traces.flatMap((t) => t.calls || [{ call_ids: t.call_ids, span_ids: t.span_ids }]),
  };
}

export default function ProvenancePage() {
  const [spans, setSpans] = useState<SpanNode[]>([]);
  const [edges, setEdges] = useState<SpanEdge[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [active, setActive] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = useState("");
  const [ancestors, setAncestors] = useState<Array<Record<string, unknown>>>([]);
  const [ancestorNote, setAncestorNote] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchGraph(), fetchAllDecisions(), fetchTraces()])
      .then(([g, d, t]) => {
        setSpans(g.nodes as SpanNode[]);
        setEdges(g.edges as SpanEdge[]);
        setDecisions(d.items);
        setTraces(t.traces);
        setSession(t.session);
        const wanted =
          typeof window !== "undefined"
            ? new URLSearchParams(window.location.search).get("trace")
            : null;
        const match = wanted && t.traces.some((x) => x.trace_id === wanted);
        setActive(match ? (wanted as string) : t.traces[0]?.trace_id || ALL);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (!selected || selected.startsWith("call:")) {
      setAncestors([]);
      setAncestorNote(
        selected ? "Decision nodes are audit records, not provenance spans." : null,
      );
      return;
    }
    let cancelled = false;
    setAncestorNote("Loading stored ancestors…");
    fetchAncestors(selected)
      .then((body) => {
        if (cancelled) return;
        setAncestors(body.ancestors);
        setAncestorNote(
          body.ancestors.length
            ? null
            : "This span has no stored ancestors. No edge was added to fill the gap.",
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setAncestors([]);
        setAncestorNote(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const trace = useMemo(() => {
    if (!traces.length) return null;
    if (active === ALL) return mergeTraces(traces);
    return traces.find((t) => t.trace_id === active) || null;
  }, [traces, active]);

  const visibleSpans = useMemo(() => {
    if (!trace) return [];
    const ids = new Set(trace.span_ids);
    return spans.filter((span) => ids.has(span.id));
  }, [spans, trace]);
  const visibleEdges = useMemo(() => {
    const ids = new Set(visibleSpans.map((span) => span.id));
    return edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  }, [edges, visibleSpans]);
  const graph = useMemo(
    () => buildTraceGraph(spans, edges, decisions, trace),
    [spans, edges, decisions, trace],
  );
  const timeline = useMemo(() => traceTimeline(graph.nodes), [graph.nodes]);
  useEffect(() => {
    if (!trace) return;
    const ids = new Set(trace.span_ids);
    const arg = spans.find((span) => ids.has(span.id) && span.kind === "TOOL_ARG");
    setSelected(arg?.id || null);
  }, [trace, spans]);

  const selectedNode = graph.nodes.find((n) => n.id === selected) || null;
  const visibleTraces = traces.filter(
    (t) =>
      !filter ||
      t.trace_id.toLowerCase().includes(filter.toLowerCase()) ||
      t.family.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="trace-layout">
      <aside className="trace-sidebar" aria-label="Sessions and traces">
        <div className="ts-section">
          <div className="ts-title">Session</div>
          <div className="ts-session">
            <span className={`ts-mode ${session?.mode || "empty"}`}>
              {session?.mode || "empty"}
            </span>
            <p>{session?.label || "No session loaded."}</p>
          </div>
        </div>
        <div className="ts-section grow">
          <div className="ts-title">
            Traces <span className="ts-count">{traces.length}</span>
          </div>
          <input
            className="ts-filter"
            placeholder="Filter traces…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter traces"
          />
          <ul className="ts-list">
            {traces.length ? (
              <li>
                <button
                  type="button"
                  className={active === ALL ? "active" : undefined}
                  onClick={() => {
                    setActive(ALL);
                    setSelected(null);
                  }}
                >
                  <span className="ts-id">All traces</span>
                  <span className="ts-meta">
                    {spans.length} spans · {decisions.length} decisions
                  </span>
                </button>
              </li>
            ) : null}
            {visibleTraces.map((t) => {
              const outcome =
                t.decision ||
                (decisions.find((d) => t.call_ids.includes(d.call_id) && d.decision === "BLOCK")
                  ? "BLOCK"
                  : "mixed");
              return (
                <li key={t.trace_id}>
                  <button
                    type="button"
                    className={active === t.trace_id ? "active" : undefined}
                    onClick={() => {
                      setActive(t.trace_id);
                      setSelected(null);
                    }}
                    title={t.label}
                  >
                    <span className="ts-id mono">{t.trace_id}</span>
                    <span className="ts-meta">
                      <span className={`ts-kind ${t.kind}`}>{t.kind}</span> {t.family}
                      <span className={`ts-dec ${outcome}`}>{outcome}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      <section className="trace-main">
        <div className="trace-head">
          <div>
            <h1>Provenance trace</h1>
            <p className="mono">
              {trace?.label || "—"}{" "}
              <span className="dim">
                · {graph.nodes.length} nodes · {graph.edges.length} edges
              </span>
            </p>
          </div>
          <div className="trace-head-note">
            Spans and decisions come from the live registry and audit store. Inferred edges are
            reconstruction evidence, never verified causation.
          </div>
        </div>
        <label className="trace-picker">
          <span>Trace</span>
          <select
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setSelected(null);
            }}
          >
            {traces.length ? <option value={ALL}>All traces</option> : null}
            {traces.map((t) => (
              <option key={t.trace_id} value={t.trace_id}>
                {t.trace_id} · {t.decision || "mixed"}
              </option>
            ))}
          </select>
        </label>
        <PageHint id="provenance" title="How to read the provenance graph">
          Each box is a span the registry stored. Arrows are stored edges. KNOWN, INFERRED, UNKNOWN
          and PARTIAL are the recorded status. Selecting a tool argument highlights the untrusted
          path that reaches it. Drag to pan and use the controls to zoom.
        </PageHint>
        {error ? <div className="banner danger">{error}</div> : null}
        {!loaded && !error ? <Skeleton label="Loading provenance" rows={4} /> : null}
        {loaded && !traces.length && !error ? (
          <div className="empty-guide">
            No runs yet. <Link href="/demo">Run a scenario</Link> or try your own text, then come
            back here to see its graph.
          </div>
        ) : null}
        {loaded ? (
          <ProvenanceFlow
            spans={visibleSpans}
            edges={visibleEdges}
            selectedId={selected}
            onSelect={setSelected}
            revealKey={trace?.trace_id || "none"}
          />
        ) : null}
        {selectedNode ? (
          <div className="trace-inspector">
            <div className="ti-head">
              <strong>{selectedNode.label}</strong>
              <span className="dim">{selectedNode.sublabel}</span>
              <button type="button" onClick={() => setSelected(null)} aria-label="Close">
                ×
              </button>
            </div>
            {selectedNode.call ? (
              <dl>
                <dt>Decision</dt>
                <dd className={`dec ${selectedNode.call.decision}`}>
                  {selectedNode.call.decision}
                </dd>
                <dt>Policy</dt>
                <dd className="mono">{selectedNode.call.policy_id || "—"}</dd>
                <dt>Provenance</dt>
                <dd>{selectedNode.call.provenance_status}</dd>
                <dt>Explanation</dt>
                <dd>{selectedNode.call.explanation}</dd>
              </dl>
            ) : (
              <dl>
                <dt>Status</dt>
                <dd>{selectedNode.span?.provenance_status}</dd>
                <dt>Agent</dt>
                <dd className="mono">{selectedNode.span?.agent_id || "—"}</dd>
                <dt>Content (redacted)</dt>
                <dd className="mono">{selectedNode.span?.content_redacted || "—"}</dd>
                <dt>Span</dt>
                <dd className="mono">{selectedNode.id}</dd>
                <dt>Stored ancestors</dt>
                <dd>
                  {ancestorNote ? <span className="dim">{ancestorNote}</span> : null}
                  {ancestors.length ? (
                    <ol className="plain-list">
                      {ancestors.map((span) => (
                        <li key={String(span.span_id)}>
                          <span className="mono">{String(span.kind || "span")}</span>
                          <span>{String(span.provenance_status || "—")}</span>
                          <span className="dim">{String(span.origin || "")}</span>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </dd>
              </dl>
            )}
          </div>
        ) : null}
      </section>

      <aside className="trace-timeline" aria-label="Timeline">
        <div className="tt-title">
          Timeline <span className="dim">UTC</span>
        </div>
        <ol>
          {timeline.map((ev, i) => (
            <li key={`${ev.at}-${i}`} className={ev.tone}>
              <span className="tt-time mono">{formatUtcTime(ev.at)}</span>
              <span className="tt-type">{ev.type}</span>
              <span className="tt-detail">{ev.detail}</span>
            </li>
          ))}
          {!timeline.length ? <li className="info">No events.</li> : null}
        </ol>
      </aside>
    </div>
  );
}
