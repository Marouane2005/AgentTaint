# Configuration reference (`agenttaint.yaml`, version 1)

`agenttaint init` writes a commented template. Every string may contain
`${NAME}` placeholders, filled from the process environment first and then from
the `.env` file next to the config. A placeholder that is set nowhere is an
error (the CLI refuses to start rather than guessing).

```yaml
version: 1
agent_id: agent_default
policy:
  file: ./policies/provenance_policy.yaml
  trust_registry: ./policies/trust_registry.yaml
storage:
  database_url: ${AGENTTAINT_DATABASE_URL}
  security_database_url: ${AGENTTAINT_SECURITY_DB_URL}
backend:
  command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "./sandbox"]
dashboard:
  host: 127.0.0.1
  port: 8080
  auth: required
```

| Key | Default | Meaning |
|-----|---------|---------|
| `version` | `1` | Config schema version. Other values are rejected. |
| `agent_id` | `agent_default` | Agent identity recorded on decisions for calls through this proxy. |
| `policy.file` | packaged default | Cedar-backed provenance policy (`engine: cedar`). Relative paths resolve from the config's directory. |
| `policy.trust_registry` | packaged default | Per-tool `default_risk` (LOW/MEDIUM/HIGH), `result_origin` and `integration_trust`. |
| `storage.database_url` | in-memory | Provenance graph and audit log (SQLAlchemy URL). Use `sqlite+pysqlite:////abs/path.db` or `postgresql+psycopg://user:pass@host/db`. In-memory loses everything on exit and cannot be shared with the dashboard. |
| `storage.security_database_url` | none | Confirmation queue and replay nonces. Required for `agenttaint approve` and dashboard approvals. May be the same database as above. |
| `backend.command` | none | Argument list (or a shell-style string) that starts the protected MCP server on stdio. |
| `dashboard.host` / `port` | `127.0.0.1` / `8080` | Bind address for `agenttaint dashboard`. |
| `dashboard.auth` | `required` | `required`: every `/api/v1` route except `/api/v1/health` needs the dashboard token. `mutations`: only POST routes. `off`: no token, allowed on loopback only. |

## Environment variables

Secrets live only in the environment (or `.env`, mode 600). Never put them in
`agenttaint.yaml` or commit them.

| Variable | Used by | Notes |
|----------|---------|-------|
| `AGENTTAINT_CONFIRM_SECRET` | proxy, approve, dashboard | HMAC key binding approvals to exact arguments. 32+ random characters; placeholders are rejected. Same value everywhere. |
| `AGENTTAINT_DASHBOARD_TOKEN` | dashboard | Read token typed into the dashboard once per browser tab. Cannot approve. |
| `AGENTTAINT_APPROVER_TOKEN` | dashboard | Separate token for the Confirmations page. Must differ from the dashboard token. Without it, dashboard approvals are disabled (CLI approval still works). |
| `AGENTTAINT_DATABASE_URL` | proxy, dashboard | Referenced by the template's `storage.database_url`. |
| `AGENTTAINT_SECURITY_DB_URL` | proxy, approve, dashboard | Referenced by `storage.security_database_url`. |
| `POSTGRES_PASSWORD` | docker compose | Password for the bundled Postgres container. |
| `AGENTTAINT_POLICY_DIR` | all | Optional directory overriding where default policy files are looked up. |
| `AGENTTAINT_UI_DIR` | dashboard | Optional path to a static dashboard build; the packaged one is used otherwise. |
| `AGENTTAINT_CORS_ORIGINS` | dashboard | Comma-separated origins allowed to call the API from another origin. Empty when the UI is served by the dashboard itself. |

The proxy strips every `AGENTTAINT_*` secret and database URL from the
environment it hands to the protected MCP server.

## Policy files

* [security_policies.md](security_policies.md) explains the provenance policy.
* [cedar_policy.md](cedar_policy.md) covers the Cedar engine and its schema.
* After editing either file, restart the proxy. Invalid policies fail closed:
  the proxy refuses to start instead of allowing calls.
