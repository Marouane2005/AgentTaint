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
| `AGENTTAINT_DASHBOARD_TOKEN` | unset | Shared secret for API mutations/reads |
| `AGENTTAINT_TEST_POSTGRES_URL` | unset | Postgres reliability tests |
| `AGENTTAINT_API_ORIGIN` | `http://127.0.0.1:8080` | Dashboard → API rewrite target |

## Security note for demos

Local demos default to `AGENTTAINT_API_AUTH=off`. For any shared host, set a
dashboard token and `AGENTTAINT_API_AUTH=required`.
