# AgentTaint audit and product plan

Status: the benchmark report bug and the false zero on the run page are
fixed on `fix/benchmark-reports-2943`. The console work (live activity,
server-side audit paging, provenance ancestors, gateway health, fixture
runs, and the darker console) follows on `feat/console-operations-2943`.

Audit of `main` at `1f38a87` (2026-11-19), before the console restyle.
The live service is the Render free web service `agenttaint-demo`, which
auto-deploys this branch and serves the static dashboard from the FastAPI
process (`AGENTTAINT_DEMO_MODE=1`).

## What is wrong with “0 available benchmark scenarios”

Two separate surfaces use the word “scenario”, and only one of them was empty.

1. **Benchmark Lab (`/benchmarks`, `GET /api/v1/benchmarks`) was empty on every
   fresh checkout, including the live site.** `load_benchmark_summary` read
   only `benchmarks/reports/report_test_*.json`. `.gitignore` excludes those
   JSON files (“Generated benchmark JSON is large; keep markdown summaries in
   git”). The committed artifacts are `report_test_*.md`, written by the same
   report writer. The directory exists, so the API answered
   `available: false` and `No benchmark reports found. Run: make benchmark`.
   Confirmed locally and on `https://agenttaint-demo.onrender.com/api/v1/benchmarks`.
   The fix reads the markdown tables (JSON still wins when both exist for the
   same report id) and returns the curated scenario catalogue next to them.
   Metrics are copied from the file. Nothing is interpolated.

2. **Run-a-scenario (`/demo`, `GET /api/v1/demo/scenarios`) is not empty.**
   The catalogue is 33 curated fixtures (one held-out case per family, plus
   reconstruction and challenge cases). A browser that executes the page
   script shows “33 available”. The static HTML is baked with an empty React
   state, so the first paint — and any client that does not run the script —
   literally says “0 available”. That counter now stays on “Loading scenarios…”
   until the request settles, and on “Unavailable” if it fails. A genuine empty
   filter says “No scenarios match this filter.”

Catalogue rows are descriptions of input fixtures. A decision appears only
after `POST /api/v1/demo/run` executes the scenario through the real gateway.

## Architecture

One Python process is the authority. The dashboard is a Next.js static export
served by that process (`apps/dashboard` → `out/`, `AGENTTAINT_UI_DIR`).
There is no second backend and no paid API on the enforcement path.

| Package | Role |
| --- | --- |
| `agenttaint_core` | Schemas, hashing, redaction, paths |
| `agenttaint_provenance` | Span store, registry, trust labels, lineage |
| `agenttaint_risk` | Tool risk tiers |
| `agenttaint_policy` | Python reference policy and Cedar engine (`agenttaint.cedar`) |
| `agenttaint_reconstruction` | Lexical, structural, optional semantic matching. Edges it adds are INFERRED |
| `agenttaint_audit` | Append-only `ToolCallDecision` rows (hash, redacted args, evidence, policy id) |
| `agenttaint_mcp_proxy` | `SecurityGateway`: label, reconstruct, evaluate, ALLOW / CONFIRM / BLOCK, then maybe forward |
| `agenttaint_agent_sdk` | Envelopes, confirmation records, nonce store |
| `agenttaint_benchmark` | Scenario JSON under `benchmarks/data/`, runner, metrics, report writer |
| `agenttaint_api` | Control plane. Does not bypass the gateway |
| `integrations/mock_*` | Email, filesystem, HTTP, shell stand-ins. The public demo wires mock email only |

Cedar returns ALLOW, CONFIRM, or BLOCK from facts the gateway computed
(risk tier, provenance status, grants, untrusted influence, registry health).
High risk with an unreachable registry fails closed. CONFIRM is a human
channel: exact argument binding, one use, expiry. The proxy exposes no
approval tool. In demo mode every confirmation route returns 403.

Provenance statuses on spans and edges are KNOWN, INFERRED, UNKNOWN, PARTIAL.
The graph export omits raw metadata. The trace view adds EVALUATED and
EXECUTED links between a decision and the spans of that call; those are
presentation links, not stored provenance edges, and the UI must keep saying so.

### Control-plane routes

| Method and path | Backing data |
| --- | --- |
| `GET /api/v1/health` | Registry probe, audit probe, demo/auth flags |
| `GET /api/v1/metrics/overview` | Audit counts and span/edge counts |
| `GET /api/v1/decisions` | Audit store, newest first, limit 1–500 |
| `GET /api/v1/decisions/{id}` | One audit row |
| `GET /api/v1/traces` | In-memory trace index for the current process |
| `GET /api/v1/graph/export` | Provenance spans and edges actually stored |
| `GET /api/v1/spans/{id}` | Span, lineage completeness, origin conflicts |
| `GET /api/v1/spans/{id}/ancestors` | Stored ancestor chain |
| `GET /api/v1/reconstruction` | Last reconstruction cache, else evidence on a recent decision |
| `GET /api/v1/benchmarks` | Report files on disk, plus scenario catalogue |
| `POST /api/v1/demo/seed` | Replays fixtures through `SecurityGateway`. Disabled against a live proxy DB |
| `POST /api/v1/session/clear` | Resets in-memory stores. 403 in the public demo |
| `GET/POST /api/v1/confirmations...` | Durable confirmation service. 403 in the public demo; otherwise approver token |
| `GET /api/v1/demo/scenarios` | Curated fixtures |
| `POST /api/v1/demo/run` | One fixture, undefended baseline plus real gateway |
| `POST /api/v1/demo/custom` | Visitor text, obedient mock proposal, real gateway |
| `POST /api/v1/waitlist`, `GET /api/v1/admin/waitlist` | Site DB. Admin header is a separate token |

Demo protections that must keep working: sliding-window rate limits, admin
token of 24+ characters on the waitlist admin routes, Paddle checkout only
when `PADDLE_CLIENT_TOKEN` was present at build time, honeypot field on the
waitlist, no approval path an agent can call.

### What the UI already wires to real data

Overview, provenance, audit, reconstruction, gateway, and the demo runner
read the routes above. Confirmations call the real approval API and, in the
public demo, show that approval is locked. The product page, legal pages, and
waitlist are real.

Gaps before this plan:

- Benchmark Lab showed no measured reports (the bug above) and could not run a scenario.
- Overview did not separate most-used tools, suspicious calls, or provenance coverage from the raw decision table. The numbers it did show come from the audit store.
- Audit filters and paging happen in the browser on a single 500-row pull.
- There is no live-activity view; decisions appear after a manual refresh.
- Reconstruction evidence is real but easy to read as proof. Explicit versus inferred has to stay obvious.
- Gateway health is a single status string. Policy-engine load is not reported.
- Free-text examples cover injection, a swapped reply address, an authorized send, and a read-only ask. They do not yet spell out a document, a payment-recipient swap, summarized instructions, an agent transfer, and a CONFIRM case as named fixtures. Scripted runs already contain those families; results must keep coming from execution.
- The trace graph is a custom zoom/pan SVG, not a third-party graph library. It only draws stored provenance edges plus the two labeled presentation links above.

### Deployment

`render.yaml` installs the workspace editable, builds the static UI, and
starts `python -m agenttaint_api` on `0.0.0.0:$PORT`. Auth is off in demo
mode. `AGENTTAINT_SITE_DB_URL` is the free Postgres used for the waitlist.
The Docker image does not copy `benchmarks/`; the hosted demo does not use
that image.

Sessions, nonces, and confirmations are in-memory unless a database URL is
set. A restart drops the demo session; startup seeds it again. Benchmark
files on disk are not part of that reset.

## Implementation order

1. **Reports and the scenario counter** (this change). Markdown reports load.
   The catalogue count is on `/api/v1/benchmarks`. The demo counter does not
   claim zero while the request is in flight.
2. **Console identity.** Keep the current CSS component layer (it is what the
   screens and tests are built on). Shift it to a darker navy field, electric
   cyan accent, green ALLOW, amber CONFIRM, red BLOCK, Inter, Lucide icons in
   the shell, and motion that respects `prefers-reduced-motion`. No extra
   glow. Landing page, shell, and navigation included.
3. **Screens on real routes.** Overview breakdowns from decisions and the
   graph export. A live-activity page that polls `/api/v1/decisions`. Provenance
   inspector follows `/api/v1/spans/{id}/ancestors` and labels evidence types.
   Audit gains server-side filter, sort, and pagination. Confirmations stay
   human-only and say when the public demo cannot approve. Reconstruction
   labels explicit versus inferred and names lexical, structural, and semantic
   channels. Gateway shows registry, audit, and policy-engine probes.
   Benchmark center lists the catalogue, runs a selected fixture through
   `/api/v1/demo/run`, and shows the measured report beside it. External
   benchmarks stay labeled “not evaluated”.
4. **Public demo fixtures.** Named examples for an injected email, a malicious
   document, a payment-recipient swap, instructions inside a summary, an
   agent-to-agent transfer, a legitimate ALLOW, and a CONFIRM. Scripted
   families run through `/api/v1/demo/run`. Free-text examples run through
   `/api/v1/demo/custom`. The mock agent stays labeled as a mock. Any step
   animation starts only after the response arrives.
5. **Verification.** Full pytest, dashboard vitest, ruff, eslint, plus
   Playwright journeys and screenshots of each main screen at desktop and
   mobile widths against the local demo-mode API.

## Limitations that stay visible

MCP confirmations, parent maps, and candidates still move in `_agenttaint`
metadata; resources, prompts, and SSE are unsupported. Nonce and confirmation
stores default to in-memory SQLite. Registry availability is a live probe,
with a manual override only in tests. AgentDojo and InjecAgent have no
published full ASR. The in-process FastMCP demo is not a multi-process
deployment. Synthetic zero-ASR figures are not general attack prevention.
This deployment is a research and portfolio demo, not a production control plane.
