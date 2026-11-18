# Changelog

All notable changes to AgentTaint. Versions follow semantic versioning.

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
