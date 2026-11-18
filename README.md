# AgentTaint

**Evidence-based information-flow enforcement for AI agents and MCP tool use.**

AgentTaint sits between agents and Model Context Protocol (MCP) tools. It tracks
provenance across transformations and agents, reconstructs possible influence on
sensitive arguments, and enforces risk-sensitive **ALLOW / BLOCK / CONFIRM**
decisions at a single gateway.

This is **not** a prompt-injection classifier and **not** a keyword filter.

> **Status (M14):** Research / demo release on a free/local stack. Synthetic
> suite + adversarial tests are reproducible. AgentDojo / InjecAgent ASR are
> **not evaluated**. Do not treat zero synthetic ASR as production attack
> prevention. Details: [docs/research_report.md](docs/research_report.md).

## One-command demo

```bash
make demo
# Dashboard → http://127.0.0.1:3000
# Click “Seed demo session”, then open Provenance / Gateway / Benchmark Lab
```

Docker Compose alternative:

```bash
make demo-compose
```

Full install notes: [docs/install.md](docs/install.md).

## Quick checks

```bash
make install
make test
make benchmark          # fixture semantic backend
make eval-m13           # M13 defense + ablation tables
```

Optional local BGE embeddings:

```bash
python3 -m pip install -e "./packages/reconstruction[semantic]"
make benchmark-bge
```

## What ships

| Layer | Packages / apps |
|-------|-----------------|
| Core | `agenttaint-core`, `provenance`, `risk`, `policy`, `audit`, `reconstruction` |
| Enforcement | `agenttaint-mcp-proxy`, `agenttaint-agent-sdk` |
| Mocks | email, filesystem, http, shell (requires Docker; refuses to run without it; resource-limited, no network, unprivileged — see `docs/mcp_compatibility_m10.md`) |
| Evaluation | `agenttaint-benchmark`, `scripts/run_m13_evaluation.py` |
| Control plane | `agenttaint-api` + Next.js dashboard (`apps/dashboard`) |

## Core research question

Can we determine whether untrusted information **materially influenced** a
dangerous agent action after summarization, paraphrase, memory, or multi-agent
delegation—and enforce policy at the MCP boundary?

Provenance is not causation. The system distinguishes **KNOWN**, **INFERRED**,
and **UNKNOWN** lineage and never silently upgrades inference to fact.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/research_report.md](docs/research_report.md) | M14 research report + completeness verdict |
| [docs/research_contribution.md](docs/research_contribution.md) | Defensible vs unsupported claims |
| [docs/related_work.md](docs/related_work.md) | CaMeL, FIDES, CapLite, NeuroTaint |
| [docs/architecture.md](docs/architecture.md) | Components, MCP design, M10–M14 notes |
| [docs/threat_model.md](docs/threat_model.md) | Assets, attackers, trust boundaries |
| [docs/limitations.md](docs/limitations.md) | Honest limits & assumptions |
| [docs/install.md](docs/install.md) | Install, demo, environment variables |
| [docs/benchmark_results_m13.md](docs/benchmark_results_m13.md) | Latest measured tables (additive) |
| [docs/m13_security_performance.md](docs/m13_security_performance.md) | M13 adversarial + ablation scope |
| [docs/external_benchmarks_m12.md](docs/external_benchmarks_m12.md) | External ASR not evaluated |
| [docs/dashboard.md](docs/dashboard.md) | Dashboard usage |
| [docs/mcp_compatibility_m10.md](docs/mcp_compatibility_m10.md) | MCP support boundary |
| [research_log/](research_log/) | Decisions and experiments |

## Design principles

1. Build the real enforcement engine first; the UI never invents decisions.
2. Free/local stack — no mandatory paid APIs.
3. Fail closed for designated high-risk ops when provenance cannot be verified.
4. Reproducible tests and benchmarks; no fabricated metrics.
5. Compare honestly to existing systems; do not claim primacy.

## License

Apache-2.0 — see [LICENSE](LICENSE).
