# Security & engineering review (post–Milestone 8 redesign)

Review scope: control-plane API, dashboard UI, audit privacy, demo isolation, dependencies, setup reproducibility. **No gateway policy was weakened.**

## Findings and fixes

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| S1 | Medium | CORS `allow_origins=["*"]` with credentials enabled | Restricted to localhost dashboard origins by default; credentials disabled; override via `AGENTTAINT_CORS_ORIGINS` |
| S2 | Medium | API bound `0.0.0.0` by default (LAN exposure) | Default host `127.0.0.1`; `make api` uses loopback; set `HOST=0.0.0.0` only for deploy |
| S3 | Low | Unbounded `limit` on decisions list | `Query(ge=1, le=500)` |
| S4 | Low | Path IDs not validated | Regex allowlist on `call_id` / `span_id` |
| S5 | Low | Mutating demo endpoints unauthenticated | Optional `AGENTTAINT_DASHBOARD_TOKEN` + `X-AgentTaint-Token` header (local-trust when unset) |
| S6 | Low | Graph export could ship long redacted previews / metadata | Truncate `content_redacted`; omit metadata blobs from graph export |
| S7 | Info | Demo and empty session share process memory | By design for local demo; labeled SIMULATED; clear resets stores; benchmarks stay on disk |
| S8 | Info | UI renders untrusted tool-derived strings | React text nodes (escaped); truncate previews; no `dangerouslySetInnerHTML` |
| S9 | Info | Audit returns redacted args + hashes | Preserved; dashboard shows hashes/redaction only |

## Explicit non-goals / residual risk

- Control plane is a **local research console**, not a multi-tenant SaaS. Without `AGENTTAINT_DASHBOARD_TOKEN`, anyone who can reach the API can seed/clear the in-memory session.
- Binding `HOST=0.0.0.0` without a token is unsuitable for untrusted networks.
- Benchmark files under `benchmarks/reports/` are world-readable on disk by design for local research.

## Verification

- `make test` / `make lint` / `make dashboard-test` / `make dashboard-lint`
- Clean install path: `make install` → `make dashboard-install` → `make api` → `make dashboard`
