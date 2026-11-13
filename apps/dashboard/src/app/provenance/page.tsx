"use client";

import { useEffect, useState } from "react";
import { ProvenanceGraph } from "@/components/ProvenanceGraph";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchGraph } from "@/lib/api";

export default function ProvenancePage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchGraph>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGraph()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="topbar">
        <div>
          <p className="eyebrow">Lineage</p>
          <h1>Provenance Explorer</h1>
          <p>
            Interactive transformation graph. Solid edges are EXPLICIT
            (instrumented). Dashed amber edges are INFERRED reconstruction links —
            never verified causation. Gap/UNKNOWN nodes use dashed borders.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      {loading ? <div className="loading">Loading provenance graph…</div> : null}
      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <h2>Graph</h2>
            <span className="panel-meta">live registry export</span>
          </div>
          <ProvenanceGraph
            nodes={(data?.nodes || []) as never[]}
            edges={(data?.edges || []) as never[]}
          />
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>Status legend</h2>
          </div>
          <div className="legend">
            {Object.entries(data?.status_legend || {}).map(([k, v]) => (
              <div key={k}>
                <span className={`pill ${k}`}>{k}</span>
                <span>{v}</span>
              </div>
            ))}
          </div>
          <div className="panel-head" style={{ marginTop: "1.35rem" }}>
            <h2>Edge meanings</h2>
          </div>
          <div className="legend">
            {Object.entries(data?.relationship_legend || {}).map(([k, v]) => (
              <div key={k}>
                <strong className="mono">{k}</strong>
                <span>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
