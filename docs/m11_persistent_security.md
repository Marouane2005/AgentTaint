# Milestone 11 — Persistent security state & reliability

## Delivered

- **SQLite default** durable nonce + confirmation stores (from M10), with atomic
  APPROVED→CONSUMED updates and provenance-context binding.
- **Postgres path:** `psycopg` optional/dev dependency, `docker-compose.yml`
  Postgres 16 service, `@pytest.mark.postgres` integration test gated on
  `AGENTTAINT_TEST_POSTGRES_URL`.
- **Per-agent envelope keys:** `AgentKeyring` so forging `sender_agent` with
  another agent's secret fails verification.
- **Control-plane auth:** `AGENTTAINT_API_AUTH=off|mutations|required`. When a
  dashboard token is configured, default mode is `required` (all routes except
  health).
- **Fail-closed:** nonce/DB path errors surface as errors; unavailable registry
  remains probed.
- **Benchmark JSON** removed from git tracking (large generated artifacts);
  markdown summaries remain.

## How to run Postgres locally

```bash
docker compose -f deploy/docker-compose.dev.yml up -d postgres
export AGENTTAINT_TEST_POSTGRES_URL=postgresql+psycopg://agenttaint:agenttaint@127.0.0.1:5432/agenttaint
pytest -m postgres
```

## Remaining limitations

- Cedar still deferred (`docs/cedar_deferred.md`).
- Compose does not yet bundle the full demo stack (API + dashboard + proxy).
- External ASR benchmarks still not evaluated.
