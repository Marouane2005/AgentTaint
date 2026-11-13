# AgentTaint

**Evidence-based information-flow enforcement for AI agents and MCP tool use.**

AgentTaint is a research-oriented security layer that sits between AI agents and Model Context Protocol (MCP) tools. It tracks provenance across transformations and agents, reconstructs possible influence on sensitive tool arguments, and enforces risk-sensitive policies (**ALLOW** / **BLOCK** / **CONFIRM**).

This is **not** a prompt-injection classifier and **not** a keyword filter.

> **Current status:** Milestones **0–8** complete: assessment through Interactive Security Dashboard. Wait for approval before further milestones. See [docs/dashboard.md](docs/dashboard.md) and [docs/benchmark_results_m7.md](docs/benchmark_results_m7.md).

## Quick start

```bash
make install
make test
make benchmark            # fixture semantic backend
# optional local BGE:
python3 -m pip install -e "./packages/reconstruction[semantic]"
make benchmark-bge
make benchmark-experiment
```

### Dashboard (Milestone 8)

```bash
make install              # includes agenttaint-api
make dashboard-install
make api                  # terminal 1 — http://127.0.0.1:8080
make dashboard            # terminal 2 — http://127.0.0.1:3000
```

Use **Seed simulated session** on Overview for a labeled demo that still runs the live SecurityGateway. Benchmark Lab reads `reports/` only — run `make benchmark` first. Details: [docs/dashboard.md](docs/dashboard.md).

No API keys required. Packages: `agenttaint-core`, `agenttaint-provenance`, `agenttaint-risk`, `agenttaint-policy`, `agenttaint-audit`, `agenttaint-reconstruction`, `agenttaint-agent-sdk`, `agenttaint-benchmark`, `agenttaint-mcp-proxy`, `agenttaint-api`, plus `agenttaint-mock-email`.

See [docs/mcp_proxy.md](docs/mcp_proxy.md), [docs/reconstruction.md](docs/reconstruction.md), [docs/security_integration.md](docs/security_integration.md), [docs/dashboard.md](docs/dashboard.md), and [docs/benchmark_results.md](docs/benchmark_results.md).

---

## Core research question

Can we determine whether untrusted information **materially influenced** a dangerous agent action after summarization, paraphrase, memory, or multi-agent delegation—and use that evidence to enforce policy at the MCP boundary?

**Important:** Provenance is not causation. The system distinguishes **KNOWN**, **INFERRED**, and **UNKNOWN** lineage and never silently upgrades inference to fact.

---

## Documentation (assessment)

| Document | Contents |
|----------|----------|
| [docs/related_work.md](docs/related_work.md) | CaMeL, FIDES, CapLite, NeuroTaint, AgentDojo, InjecAgent |
| [docs/threat_model.md](docs/threat_model.md) | Assets, attackers, trust boundaries, objectives |
| [docs/feasibility.md](docs/feasibility.md) | What we can guarantee vs estimate |
| [docs/architecture.md](docs/architecture.md) | Components, schemas, APIs, MCP design |
| [docs/provenance_model.md](docs/provenance_model.md) | Epistemic model |
| [docs/security_policies.md](docs/security_policies.md) | Policy principles + M5 rules |
| [docs/security_integration.md](docs/security_integration.md) | Guarantees vs SDK requirements |
| [docs/benchmark_methodology.md](docs/benchmark_methodology.md) | Protocol, splits, metrics |
| [docs/benchmark_results.md](docs/benchmark_results.md) | M6 measured tables |
| [docs/benchmark_results_m7.md](docs/benchmark_results_m7.md) | M7 expansion, BGE, variability |
| [docs/research_contribution.md](docs/research_contribution.md) | Honest contribution assessment |
| [docs/mvp.md](docs/mvp.md) | Smallest hypothesis-testing slice |
| [docs/implementation_plan.md](docs/implementation_plan.md) | Ordered tasks + acceptance criteria |
| [docs/free_development_plan.md](docs/free_development_plan.md) | Local-first stack, hardware, licenses |
| [docs/benchmark_methodology.md](docs/benchmark_methodology.md) | Evaluation protocol |
| [docs/limitations.md](docs/limitations.md) | Honest limits |
| [docs/mcp_proxy.md](docs/mcp_proxy.md) | MCP proxy supported features & limits |
| [docs/reconstruction.md](docs/reconstruction.md) | Reconstruction channels, ablation, limits |
| [docs/dashboard.md](docs/dashboard.md) | Interactive security dashboard (M8) |
| [research_log/](research_log/) | Decisions, failures, experiments |

---

## Design principles (short)

1. Build the real enforcement engine first; UI never invents decisions.  
2. Free/local stack — no mandatory paid APIs.  
3. Fail closed for designated high-risk ops when provenance cannot be verified.  
4. Reproducible tests and benchmarks; no fabricated metrics.  
5. Compare honestly to existing systems; do not claim primacy.

---

## Roadmap (summary)

1. Provenance registry  
2. MCP proxy + mock tools  
3. Transformation graph  
4. Reconstruction + ablation  
5. Cross-agent SDK + policy + confirmation  
6. Benchmarks  
7. Benchmark expansion (M7)  
8. Dashboard (M8) — done; awaiting approval  
9. Research release  

---

## License

Apache-2.0 (intended; `LICENSE` file added with first implementation milestone).
