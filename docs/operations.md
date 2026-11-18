# Operations: deploy, upgrade, back up, rotate keys, check health

## Deployment options

| Option | When |
|--------|------|
| `pip` + `agenttaint proxy` on the client machine, SQLite | One person, one machine. Simplest. |
| `docker compose up -d` (Postgres + dashboard), proxy via pip or `docker compose run -i proxy` | A team, a shared dashboard, durable storage. |

### Docker Compose stack

From the release bundle directory (or a source checkout):

```bash
agenttaint init .                 # or: copy agenttaint.yaml + policies/, create .env yourself
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/api/v1/health
```

Services:

| Service | What | Exposed |
|---------|------|---------|
| `postgres` | Postgres 16, volume `pgdata` | not published |
| `dashboard` | control-plane API and dashboard UI (one origin) | `127.0.0.1:8080` |
| `proxy` | MCP proxy on stdio, started per client session | stdio only |

Secure defaults: secrets only from `.env` (compose refuses to start when one is
missing), non-root user (uid 10001), read-only root filesystem, all capabilities
dropped, `no-new-privileges`, `/tmp` mounted `noexec`, API auth `required`, and
the dashboard bound to loopback. For remote access put a TLS reverse proxy
(Caddy, nginx) in front of `127.0.0.1:8080`; do not publish the port directly.

The image installs Node.js so the proxy can launch `npx` MCP servers; build
with `--build-arg WITH_NODE=0` if you do not need it.

## Health checks

| Check | How | Healthy |
|-------|-----|---------|
| Control plane | `GET /api/v1/health` (no token needed) | `{"status": "ok", "registry_ok": true, "audit_ok": true}` |
| Container | Docker `HEALTHCHECK` built into the image (same endpoint) | `docker compose ps` shows `healthy` |
| Postgres | `pg_isready` healthcheck in compose | `healthy` |
| Proxy | Your MCP client lists the protected server's tools plus `agenttaint.preview` and `agenttaint.audit_summary` | tools listed |
| Approvals | `agenttaint approve --config agenttaint.yaml list` | exits 0 |

`status: "degraded"` means the provenance or audit store is unreachable. The
proxy fails closed in that state: HIGH-risk calls are blocked, not allowed.

## Backups

All state is in the two databases from `storage` (often the same one).

Postgres (compose):

```bash
docker compose exec -T postgres pg_dump -U agenttaint -Fc agenttaint > agenttaint-$(date +%F).dump
# restore into an empty database
docker compose exec -T postgres pg_restore -U agenttaint -d agenttaint --clean < agenttaint-2026-01-31.dump
```

SQLite:

```bash
sqlite3 agenttaint.db ".backup agenttaint-$(date +%F).db"
sqlite3 agenttaint-security.db ".backup agenttaint-security-$(date +%F).db"
```

Also back up `agenttaint.yaml`, `policies/` and `.env` (store `.env` encrypted:
it holds the secrets). Audit records keep argument hashes and redacted values,
not raw arguments, but they still describe what your agents did: treat backups
as sensitive.

## Key rotation

```bash
agenttaint init . --rotate        # new confirm secret, dashboard and approver tokens
docker compose up -d              # or restart `agenttaint dashboard` / the MCP client
```

* Rotating `AGENTTAINT_CONFIRM_SECRET` invalidates every pending confirmation
  (their HMAC no longer verifies). Approve or deny the queue first if needed.
* Rotating the dashboard or approver token signs out every browser tab.
* `POSTGRES_PASSWORD`: change it inside Postgres first
  (`docker compose exec postgres psql -U agenttaint -c "ALTER USER agenttaint PASSWORD '...'"`),
  then update `.env` and `docker compose up -d`.

Rotate after anyone with access to `.env` leaves, and at least yearly.

## Upgrades

1. Read `CHANGELOG.md` for the new version.
2. Back up (above).
3. Verify and unpack the new bundle (`sha256sum -c`).
4. pip installs: `pip install --upgrade --no-index --find-links wheels agenttaint`.
   Compose: copy the new `Dockerfile`/`wheels/` into place, then
   `docker compose build && docker compose up -d`.
5. Check `GET /api/v1/health` and `agenttaint --version`.

Database tables are created automatically on start. The plan for 1.x is
additive schema changes only; if a release ever needs a manual migration, its
CHANGELOG entry says so. To roll back, reinstall the previous bundle and restore the
backup taken in step 2.

## Logs

The proxy writes logs to stderr (stdout is the MCP protocol). The dashboard logs
requests via uvicorn. Neither logs secrets or raw tool arguments.
