# AgentTaint Interactive Security Dashboard (Milestone 8)

Local-first control plane for inspecting **real** provenance, reconstruction, gateway decisions, and on-disk benchmark reports. The UI never invents ALLOW / BLOCK / CONFIRM outcomes or ASR numbers.

## Architecture

```
Browser (Next.js 15)  --rewrite /api/*-->  FastAPI (agenttaint-api)
                                              |
                                              +-- AuditStore / DecisionEngine
                                              +-- ProvenanceStore + graph export
                                              +-- ReconstructionService (read-only inspect)
                                              +-- reports/*.json (benchmark lab)
```

- **SecurityGateway is unchanged.** Demo seeding runs the live gateway with HMAC envelopes; it does not bypass policy.
- **Demo sessions are labeled `SIMULATED SCENARIO`.** They produce real enforcement records against mock tools, not production traffic.
- **Benchmark Lab** loads files under `reports/` only. If no reports exist, the UI shows an empty state and points at `make benchmark`. Synthetic lab metrics are never framed as real-world claims.

## Sections

Thin top navigation; dark navy/cyan console theme. Every view reads the real
audit store, provenance registry and trace index; nothing is hand-authored.

| Page | Contents |
| --- | --- |
| **Overview** (`/`) | KPI tiles, decision timeline (stacked by ALLOW/CONFIRM/BLOCK over the real time range, UTC), four risk gauges (block rate, human review load, unverified provenance, inferred lineage), destination map (agents → tools → destination class), risk-tier donut, top policies, recent decisions |
| **Provenance** (`/provenance`) | Trace explorer: left sidebar of the session and its traces, left-to-right layered DAG (dagre) with labelled columns, zoom/pan and fit controls, "flows by source" popover, legend of node types and edge kinds, click-to-inspect, right-hand timeline of spans and decisions |
| **Audit** (`/audit`) | Filterable decision/audit table with redacted arguments, argument hash, evidence and explanation |
| **Confirmations** (`/confirmations`) | Human-only approval screen for pending CONFIRM decisions (see below) |
| Reconstruction, Gateway, Benchmarks | Unchanged views, restyled |

Screenshots: [docs/screenshots](screenshots/README.md).

### Node and edge styles (provenance page)

- Grey diamond: source or input (user instruction, tool result that feeds later steps)
- Green circle: agent message (cross-agent delegation)
- Magenta rounded square: tool step or memory (summary, extract, rewrite, memory, gap)
- Yellow square: output or sink (tool argument, result of an executed call)
- Blue node: final action, one per gateway decision, with its ALLOW/CONFIRM/BLOCK badge
- Solid blue edge: explicit lineage. Dashed amber: inferred by reconstruction (not
  verified causation). Cyan: argument evaluated by the gateway. Dotted: tool executed.

Address values are redacted in the audit store, so the destination map groups by
destination class (email recipient, web endpoint, IP, filesystem, payment), not by
geography.

### Human-only approvals

- Set `AGENTTAINT_APPROVER_TOKEN` (different from `AGENTTAINT_DASHBOARD_TOKEN`; the
  API refuses to start approvals if they are equal). The approval routes accept only
  the approver token, sent as `X-AgentTaint-Approver`. The dashboard read token,
  which may be bundled into the UI via `NEXT_PUBLIC_AGENTTAINT_TOKEN`, cannot approve.
- The approval screen asks a person to type the approver token. It lives in memory
  for that tab only; it is never stored, logged or bundled.
- Agents cannot reach this channel: the MCP proxy exposes no approval tool (security
  probe W2), approvals are bound to tool, arguments hash and agent, single-use and
  time-limited.
- Without `AGENTTAINT_APPROVER_TOKEN`, the legacy behaviour applies (dashboard token).
- With `AGENTTAINT_SECURITY_DB_URL` and an approver token configured, the demo seed
  queues its CONFIRM decisions in the durable confirmation store.

### Provenance graph semantics

- Solid edges: recorded relationships with explicit or structural evidence.
- Dashed / amber edges: **INFERRED** — candidate influence, **not** verified lineage.
- Gaps (missing parents, UNKNOWN status): reconstruction could not establish a chain; policy may fail closed for high-risk ops.
- Selecting a node or edge shows kind, origin, agent, relationship, and legend text from the API.

## Setup

```bash
# Python packages (includes agenttaint-api)
make install

# Dashboard dependencies (once)
make dashboard-install
```

## Usage

Terminal 1 — API (binds `0.0.0.0:$PORT`, default 8080):

```bash
make api
# or: PORT=8080 python3 -m agenttaint_api
```

Terminal 2 — UI:

```bash
make dashboard
# open http://127.0.0.1:3000
```

Optional: set `AGENTTAINT_API_ORIGIN` if the API is not on `http://127.0.0.1:8080` (used by Next.js rewrites).

### Demo seed

On Overview, **Seed simulated session** calls `POST /api/v1/demo/seed`. That:

1. Resets in-memory stores for a fresh demo session.
2. Runs a short mock email flow through the **real** SecurityGateway (multi-agent
   exfiltration attempt, a granted benign send, and two sends by an uninstrumented
   agent that end in CONFIRM).
3. Replays 16 held-out test-split and 4 challenge-split synthetic benchmark
   scenarios through real gateways (combined defense) into the same stores, one
   trace per scenario (`AGENTTAINT_SEED_SCENARIOS`, default 16; 0 disables).
4. Labels the session as simulated in the banner and API `session.notes`.

Clear with **Clear session** (`POST /api/v1/session/clear`).

### Benchmarks

```bash
make benchmark          # writes reports/
# then refresh Benchmark Lab
```

## API surface (`/api/v1`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | Liveness |
| GET | `/metrics/overview` | Decision tallies + status |
| GET | `/graph/export` | Nodes/edges + status legend |
| GET | `/reconstruction` | Channel evidence + disclaimer |
| GET | `/decisions` | Audit trail (redacted args) |
| GET | `/traces` | Seeded traces: span and decision ids per scenario and per call |
| GET | `/confirmations` | Pending confirmations (approver token) |
| POST | `/confirmations/{id}/approve` · `/deny` | Human decision (approver token) |
| GET | `/benchmarks` | Disk reports + synthetic disclaimer |
| POST | `/demo/seed` | Simulated scenario via live gateway |
| POST | `/session/clear` | Empty session |

## Tests

```bash
make test              # includes tests/unit/test_api_dashboard.py
make dashboard-test    # Vitest (derive, layout, TraceGraph, approval screen)
make dashboard-lint
make test-all
# Screenshots of every page (needs the API + dashboard running, seeded):
cd apps/dashboard && AGENTTAINT_APPROVER_TOKEN=... npm run screenshots
```

## Security notes (local-trust)

- `make api` binds **127.0.0.1** by default. For containers/Render set `HOST=0.0.0.0`.
- CORS defaults to localhost dashboard origins (`AGENTTAINT_CORS_ORIGINS` to override).
- Optional mutation gate: set `AGENTTAINT_DASHBOARD_TOKEN` on the API and
  `NEXT_PUBLIC_AGENTTAINT_TOKEN` for the Next.js client.
- See [docs/security_review_m8.md](security_review_m8.md).

## Limitations

- In-memory session only; process restart clears live audit/provenance (benchmark files on disk persist).
- Demo seed is a fixed mock-email scenario for UX, not a substitute for MCP proxy integration tests.
- Graph layout is layered SVG for clarity, not a full graph-database explorer.
- Dashboard is read-mostly; it does not offer operator overrides that weaken the gateway.
- Without a dashboard token, anyone who can reach the loopback API can seed/clear the session.
