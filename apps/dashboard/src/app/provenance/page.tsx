"use client";

import { useEffect, useState } from "react";
import { ProvenanceGraph } from "@/components/ProvenanceGraph";
import { SessionBanner } from "@/components/SessionBanner";
import { fetchGraph } from "@/lib/api";

export default function ProvenancePage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchGraph>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraph()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Provenance Explorer</h1>
          <p>
            Interactive lineage graph. Solid edges are EXPLICIT (instrumented). Dashed
            amber edges are INFERRED reconstruction links — not verified causation.
          </p>
        </div>
      </div>
      {error ? <div className="banner danger">{error}</div> : null}
      <SessionBanner session={data?.session} />
      <div className="two-col">
        <div className="panel">
          <h2>Graph</h2>
          <ProvenanceGraph
            nodes={(data?.nodes || []) as never[]}
            edges={(data?.edges || []) as never[]}
          />
        </div>
        <div className="panel">
          <h2>Status legend</h2>
          <div className="legend">
            {Object.entries(data?.status_legend || {}).map(([k, v]) => (
              <div key={k}>
                <span className={`pill ${k}`}>{k}</span>
                <span>{v}</span>
              </div>
            ))}
          </div>
          <h2 style={{ marginTop: "1.25rem" }}>Edge meanings</h2>
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
