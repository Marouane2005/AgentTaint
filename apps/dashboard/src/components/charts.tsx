"use client";

import { formatUtcTime, type FlowLink, type TimelineBin } from "@/lib/derive";

export const DECISION_COLORS: Record<string, string> = {
  ALLOW: "#2fd39a",
  CONFIRM: "#f2b937",
  BLOCK: "#ff5f6d",
};

/** Semicircle gauge for a 0..1 ratio. */
export function Gauge({
  value,
  label,
  hint,
  color = "#22d3ee",
}: {
  value: number;
  label: string;
  hint: string;
  color?: string;
}) {
  const v = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  const r = 52;
  const cx = 64;
  const cy = 64;
  const angle = Math.PI * (1 - v);
  const x = cx + r * Math.cos(angle);
  const y = cy - r * Math.sin(angle);
  return (
    <div className="gauge" role="meter" aria-valuenow={Math.round(v * 100)} aria-label={label}>
      <svg viewBox="0 0 128 76" width="100%">
        <path
          d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}`}
          stroke="#1b2a44"
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
        />
        {v > 0 ? (
          <path
            d={`M${cx - r},${cy} A${r},${r} 0 0 1 ${x},${y}`}
            stroke={color}
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 4px ${color})` }}
          />
        ) : null}
        <text x={cx} y={cy - 6} textAnchor="middle" className="gauge-value">
          {Math.round(v * 100)}%
        </text>
      </svg>
      <div className="gauge-label">{label}</div>
      <div className="gauge-hint">{hint}</div>
    </div>
  );
}

export function TimelineChart({ bins, widthMs }: { bins: TimelineBin[]; widthMs: number }) {
  const W = 640;
  const H = 190;
  const pad = { l: 34, r: 10, t: 12, b: 28 };
  const max = Math.max(1, ...bins.map((b) => b.ALLOW + b.CONFIRM + b.BLOCK));
  const bw = bins.length ? (W - pad.l - pad.r) / bins.length : 0;
  const yScale = (n: number) => ((H - pad.t - pad.b) * n) / max;
  if (!bins.length) return <div className="empty">No decisions yet.</div>;
  const ticks = [0, Math.ceil(max / 2), max];
  return (
    <div className="timeline-chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Decision timeline">
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={H - pad.b - yScale(t)}
              y2={H - pad.b - yScale(t)}
              stroke="#16243b"
            />
            <text x={pad.l - 6} y={H - pad.b - yScale(t) + 3} textAnchor="end" className="axis">
              {t}
            </text>
          </g>
        ))}
        {bins.map((b, i) => {
          let y = H - pad.b;
          return (
            <g key={b.start}>
              {(["BLOCK", "CONFIRM", "ALLOW"] as const).map((k) => {
                const h = yScale(b[k]);
                y -= h;
                return h ? (
                  <rect
                    key={k}
                    x={pad.l + i * bw + 1.5}
                    y={y}
                    width={Math.max(1, bw - 3)}
                    height={h}
                    fill={DECISION_COLORS[k]}
                    rx={1.5}
                    opacity={0.92}
                  >
                    <title>{`${k} ${b[k]} @ ${formatUtcTime(b.start)} UTC`}</title>
                  </rect>
                ) : null;
              })}
            </g>
          );
        })}
        {[0, Math.floor(bins.length / 2), bins.length - 1].map((i) => (
          <text
            key={i}
            x={pad.l + i * bw + bw / 2}
            y={H - 8}
            textAnchor="middle"
            className="axis"
          >
            {formatUtcTime(bins[i].start)}
          </text>
        ))}
      </svg>
      <div className="chart-foot">
        {bins.length} bins × {widthMs} ms · times in UTC · stacked by decision
      </div>
    </div>
  );
}

export function Donut({ data, colors }: { data: Record<string, number>; colors: Record<string, string> }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  const r = 44;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="donut">
      <svg viewBox="0 0 120 120" width="120" height="120" role="img" aria-label="Risk tier mix">
        <circle cx="60" cy="60" r={r} stroke="#132038" strokeWidth="14" fill="none" />
        {entries.map(([k, v]) => {
          const len = (v / (total || 1)) * c;
          const el = (
            <circle
              key={k}
              cx="60"
              cy="60"
              r={r}
              stroke={colors[k] || "#5b8fd4"}
              strokeWidth="14"
              fill="none"
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 60 60)"
            />
          );
          offset += len;
          return el;
        })}
        <text x="60" y="58" textAnchor="middle" className="donut-total">
          {total}
        </text>
        <text x="60" y="74" textAnchor="middle" className="axis">
          calls
        </text>
      </svg>
      <ul className="donut-legend">
        {entries.map(([k, v]) => (
          <li key={k}>
            <i style={{ background: colors[k] || "#5b8fd4" }} />
            {k} <b>{v}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BarList({ data, max = 6 }: { data: Record<string, number>; max?: number }) {
  const entries = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, max);
  const top = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <ul className="barlist">
      {entries.map(([k, v]) => (
        <li key={k}>
          <span className="mono" title={k}>
            {k}
          </span>
          <span className="bar">
            <span style={{ width: `${(v / top) * 100}%` }} />
          </span>
          <b>{v}</b>
        </li>
      ))}
    </ul>
  );
}

/**
 * Agents → tools → destination classes, link width by call count and colour
 * by gateway decision. Addresses are redacted in the audit store, so
 * destinations are grouped by class rather than plotted geographically.
 */
export function DestinationMap({
  agents,
  tools,
  destinations,
  links,
}: {
  agents: string[];
  tools: string[];
  destinations: string[];
  links: FlowLink[];
}) {
  const W = 640;
  const cols = [agents, tools, destinations];
  const rows = Math.max(1, ...cols.map((c) => c.length));
  const H = Math.max(180, rows * 46 + 40);
  const xs = [90, W / 2, W - 120];
  const pos = new Map<string, { x: number; y: number }>();
  cols.forEach((col, ci) => {
    const gap = (H - 40) / Math.max(1, col.length);
    col.forEach((id, i) => pos.set(id, { x: xs[ci], y: 30 + gap * i + gap / 2 }));
  });
  const max = Math.max(1, ...links.map((l) => l.count));
  const offsets: Record<string, number> = { ALLOW: -4, CONFIRM: 0, BLOCK: 4 };
  if (!links.length) return <div className="empty">No calls yet.</div>;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Destination map">
      {["AGENTS", "TOOLS", "DESTINATIONS"].map((t, i) => (
        <text key={t} x={xs[i]} y={14} textAnchor="middle" className="axis">
          {t}
        </text>
      ))}
      {links.map((l) => {
        const a = pos.get(l.from);
        const b = pos.get(l.to);
        if (!a || !b) return null;
        const o = offsets[l.decision] || 0;
        const mx = (a.x + b.x) / 2;
        return (
          <path
            key={`${l.from}-${l.to}-${l.decision}`}
            d={`M${a.x + 10},${a.y + o} C${mx},${a.y + o} ${mx},${b.y + o} ${b.x - 10},${b.y + o}`}
            stroke={DECISION_COLORS[l.decision] || "#5b8fd4"}
            strokeWidth={1 + (5 * l.count) / max}
            fill="none"
            opacity={0.75}
          >
            <title>{`${l.from} → ${l.to}: ${l.decision} × ${l.count}`}</title>
          </path>
        );
      })}
      {[...pos.entries()].map(([id, p]) => {
        const [kind, name] = [id.split(":")[0], id.slice(id.indexOf(":") + 1)];
        return (
          <g key={id} transform={`translate(${p.x},${p.y})`}>
            <circle r={9} className={`dm-node ${kind}`} />
            <text
              x={kind === "dest" ? 14 : kind === "agent" ? -14 : 0}
              y={kind === "tool" ? -14 : 4}
              textAnchor={kind === "dest" ? "start" : kind === "agent" ? "end" : "middle"}
              className="dm-label"
            >
              {name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
