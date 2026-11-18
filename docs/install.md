# Install guide

Free/local stack. No paid APIs required for core enforcement, tests, or the
dashboard demo.

## Requirements

| Profile | CPU | RAM | Software |
|---------|-----|-----|----------|
| Core tests | 2 vCPU | 4 GB | Python 3.12+, Make |
| Dashboard demo | 4 vCPU | 8 GB | + Node.js 22+, npm |
| Optional BGE semantic | 4 vCPU | 8–16 GB | + PyTorch CPU + sentence-transformers |
| Optional Postgres | +1 GB | Docker |

GPU is not required.

## Local install

```bash
git clone https://github.com/Marouane2005/AgentTaint.git
cd AgentTaint
make install
make test
```

Dashboard:

```bash
make dashboard-install
make api          # terminal 1 — http://127.0.0.1:8080
make dashboard    # terminal 2 — http://127.0.0.1:3000
```

Or one command:

```bash
make demo
```

## Docker Compose demo

```bash
make demo-compose
# API  http://127.0.0.1:8080
# UI   http://127.0.0.1:3000
# optional: COMPOSE_PROFILES=postgres make demo-compose
```

Stop with `docker compose --profile demo down`.

## Benchmarks

```bash
make benchmark                 # fixture embedder (CI-safe)
make eval-m13                  # M13 defense + ablation report
# optional:
python3 -m pip install -e "./packages/reconstruction[semantic]"
make benchmark-bge
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENTTAINT_DATA_DIR` | `.agenttaint/dashboard` | API SQLite / session data |
| `AGENTTAINT_BENCHMARKS_DIR` | `benchmarks/reports` | Benchmark Lab JSON/MD |
| `AGENTTAINT_API_AUTH` | `off` / `required` if token set | Control-plane auth mode |
| `AGENTTAINT_DASHBOARD_TOKEN` | unset | Shared secret for API mutations/reads; **always** required by the approval endpoints |
| `AGENTTAINT_CONFIRM_SECRET` | **none (required)** | HMAC secret for confirmations; proxy refuses to start without it (≥32 chars, not a placeholder) |
| `AGENTTAINT_SECURITY_DB_URL` | in-memory SQLite | Durable confirmation/nonce store; use a file or Postgres URL so the CLI/API can approve from another process |
| `AGENTTAINT_TEST_POSTGRES_URL` | unset | Postgres reliability tests |
| `AGENTTAINT_API_ORIGIN` | `http://127.0.0.1:8080` | Dashboard → API rewrite target |

## Confirmation secret and out-of-band approval

There is no default confirmation secret. Generate one per deployment:

```bash
export AGENTTAINT_CONFIRM_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export AGENTTAINT_SECURITY_DB_URL="sqlite+pysqlite:///$PWD/.agenttaint/security.db"
```

`make demo` generates both for each run and writes them (with a random operator
token) to `.agenttaint/demo/operator.env` (git-ignored, mode 0600).

The agent cannot approve its own CONFIRM decisions. A human approves through:

```bash
source .agenttaint/demo/operator.env
python3 -m agenttaint_agent_sdk.confirm_cli list
python3 -m agenttaint_agent_sdk.confirm_cli approve <confirmation_id>
# or, via the control plane:
curl -X POST -H "X-AgentTaint-Token: $AGENTTAINT_DASHBOARD_TOKEN" \
  http://127.0.0.1:8080/api/v1/confirmations/<confirmation_id>/approve
```

The agent then retries the identical call with `_agenttaint.confirmation_id`.

## Security note for demos

Local demos default to `AGENTTAINT_API_AUTH=off`. For any shared host, set a
dashboard token and `AGENTTAINT_API_AUTH=required`.
