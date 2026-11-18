"use client";

import type { Decision } from "@/lib/api";
import { formatUtcTime, parseTs } from "@/lib/derive";

export function DecisionTable({
  rows,
  onSelect,
  selectedId,
}: {
  rows: Decision[];
  onSelect?: (d: Decision) => void;
  selectedId?: string | null;
}) {
  if (!rows.length) {
    return <div className="empty">No decisions yet. Seed the demo or connect a live proxy.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Agent</th>
            <th>Tool</th>
            <th>Risk</th>
            <th>Provenance</th>
            <th>Decision</th>
            <th>Policy</th>
            <th className="num">Latency</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr
              key={d.call_id}
              className={selectedId === d.call_id ? "selected" : undefined}
              onClick={onSelect ? () => onSelect(d) : undefined}
              style={onSelect ? { cursor: "pointer" } : undefined}
            >
              <td className="mono">{formatUtcTime(parseTs(d.created_at))}</td>
              <td className="mono">{d.agent_id || "—"}</td>
              <td className="mono">{d.tool}</td>
              <td>
                <span className={`tier ${d.risk_tier}`}>{d.risk_tier}</span>
              </td>
              <td>
                <span className={`pill ${d.provenance_status}`}>{d.provenance_status}</span>
              </td>
              <td>
                <span className={`dec ${d.decision}`}>{d.decision}</span>
              </td>
              <td className="mono small">{d.policy_id || "—"}</td>
              <td className="num mono">{d.latency_ms ?? "—"} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
