# Changelog

All notable changes to AgentTaint. Versions follow semantic versioning.

## Unreleased

### Security
- Reconstruction: semantic similarity alone can no longer promote emails, URLs, file paths
  or shell commands to INFERRED; it needs weak structural/domain overlap or explicit
  session context. Lists and nested values are now reconstructed leaf by leaf.
- Proxy: `session_id` is bound to the connection (caller-supplied values are rejected);
  malformed `_agenttaint` metadata is rejected instead of silently dropped; declared parent
  spans are verified against the registry and calling agent; declared lineage and
  caller-supplied candidates can no longer switch off session-wide reconstruction; the
  reconstruction corpus is isolated per agent/session; `agenttaint.*` tool names cannot be
  shadowed by a backend; `agenttaint.preview` is read-only.
- Confirmations: `approval_token` is now required to execute an approved call (the gateway
  no longer reads it from the stored record). `agenttaint approve` and the approve API
  response show it to the approver. Retried calls reuse their pending confirmation and each
  agent has a pending-confirmation cap. Approvals are released if the request is cancelled
  before the backend call.
- Grants: authority arguments now include `cc`, `bcc`, `cwd`, `args`, `uri`, `target`,
  `recipients`, `endpoint`; list values need a grant per element; paths and commands are
  compared case-sensitively.
- Cedar/Python policy ids are unique: `allow-user-authorized-authority` is split into
  `allow-high-user-authorized-authority` and `allow-medium-user-authorized-authority`, and
  `allow-low-medium` into `allow-medium` and `allow-low`.

- Proxy: policy evaluation, labelling and audit run on worker threads, so a slow
  evaluation (embeddings, database) no longer stalls the event loop; gateway decisions are
  serialised so concurrent replays of a single-use approval execute at most once.
- Audit: an ALLOW is written to the audit log before the call is forwarded and updated with
  the outcome (write-ahead), so a crash or cancellation mid-call still leaves a record.
- Reconstruction: declared lineage is additional evidence, never a bypass. Reconstruction
  runs for every MEDIUM/HIGH call in every gateway mode and the session corpus is always
  included; a reconstruction miss on an argument whose lineage was declared no longer
  downgrades it to UNKNOWN.
- Reconstruction: addresses spelled out in prose ("alice at evil dot com") are matched
  (MODERATE support) only when both the local part and the spelled domain appear in order.
- Confirmation request check-and-insert is atomic (no cap overshoot or duplicate requests
  under concurrency).

### Fixed
- Benchmark runner no longer monkey-patches the gateway's private evidence method; the
  ablation is an explicit `reconstruction_ablation` gateway field and the benchmark now
  exercises the same evidence path as the proxy.

### Changed
- Relicensed the project under the Apache License 2.0 (license metadata, READMEs,
  quickstart and build scripts). The product site, checkout, waitlist, terms and refund
  pages are unchanged.
- New CLI commands `connect`, `doctor` and `log`; color-coded decisions; actionable errors.
- Dashboard: friendly API-unavailable errors, loading/empty states, live-refreshing
  confirmations queue that shows the single-use approval token once, clearer provenance
  flow explanation.

## 1.0.0 — 2026-11-18

First commercial release (AgentTaint Pro, self-hosted).

### Added
- `agenttaint` command (`pip install agenttaint`): `init`, `proxy --config`,
  `approve`, `dashboard`, `version`.
- `agenttaint.yaml` configuration with `${ENV}` placeholders and a sibling
  `.env` (created with mode 600, values never printed); `init --rotate` rotates
  the confirmation secret and dashboard/approver tokens.
- Production `Dockerfile` (non-root, read-only root, healthcheck) and
  `docker-compose.yml` with Postgres, the control plane and an on-demand stdio
  proxy; all secrets required from the environment.
- Dashboard served by the control plane itself from a static build, with a
  per-tab dashboard-token prompt when API auth is required.
- The dashboard reads the proxy's database (`AGENTTAINT_DATABASE_URL`) and shows
  live decisions; demo seeding is refused in that mode.
- Default policy and trust registry shipped inside `agenttaint-core`, so wheel
  installs work without a source checkout.
- Release bundle script (`scripts/build_release.sh`), quickstart, configuration
  reference and operations guide.

- Public demo mode (`AGENTTAINT_DEMO_MODE=1`): runnable synthetic scenarios
  (undefended vs AgentTaint), approvals and session resets locked, per-client
  and global rate limits; product site with pricing, limitations, terms,
  privacy and refund pages; Pro waitlist stored in the database with a
  token-protected admin view; Paddle overlay checkout when
  `PADDLE_CLIENT_TOKEN` is set.
- Console overview moved to `/overview`.

### Changed
- All packages versioned 1.0.0. The source workspace project is now
  `agenttaint-workspace`; the name `agenttaint` belongs to the CLI distribution.
- License changed to the AgentTaint Commercial License (see `LICENSE`).
- The proxy also strips `AGENTTAINT_APPROVER_TOKEN` and `AGENTTAINT_ADMIN_TOKEN`
  from the protected server's environment.
- Development compose file moved to `deploy/docker-compose.dev.yml`.

### Included from the research milestones (M1–M15)
- Provenance registry with KNOWN / INFERRED / UNKNOWN / PARTIAL evidence;
  inferred links are never promoted to known.
- Cedar-backed provenance policy (ALLOW / CONFIRM / BLOCK), failing closed.
- Out-of-band, argument-bound, single-use confirmations.
- Reconstruction signals for broken lineage (fixture and optional BGE embedder).
- Dockerized shell sandbox, Postgres persistence, multi-process MCP proxy.
- Synthetic benchmark suite and a sampled AgentDojo run with a real model; see
  `docs/technical_report.md` and `docs/limitations.md` for what these do and do
  not show.
