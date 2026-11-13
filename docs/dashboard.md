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

| Route | Purpose |
|-------|---------|
| `/` | Overview — decision counts, recent events, system status |
| `/provenance` | Interactive provenance graph (KNOWN / INFERRED / UNKNOWN / PARTIAL) |
| `/reconstruction` | Lexical / structural / semantic evidence with epistemic labels |
| `/gateway` | Intercepted MCP-style calls, policy verdicts, confirmations, audit |
| `/benchmarks` | Baselines, ASR, utility, provenance metrics, latency, ablations |

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
2. Runs a short mock email flow through the **real** SecurityGateway.
3. Labels the session as simulated in the banner and API `session.notes`.

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
| GET | `/benchmarks` | Disk reports + synthetic disclaimer |
| POST | `/demo/seed` | Simulated scenario via live gateway |
| POST | `/session/clear` | Empty session |

## Tests

```bash
make test              # includes tests/unit/test_api_dashboard.py
make dashboard-test    # Vitest (ProvenanceGraph)
make dashboard-lint
make test-all
```

## Limitations

- In-memory session only; process restart clears live audit/provenance (benchmark files on disk persist).
- Demo seed is a fixed mock-email scenario for UX, not a substitute for MCP proxy integration tests.
- Graph layout is layered SVG for clarity, not a full graph-database explorer.
- Dashboard is read-mostly; it does not offer operator overrides that weaken the gateway.
