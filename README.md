# AgentTaint

**Evidence-based information-flow enforcement for AI agents and MCP tool use.**

AgentTaint is a research-oriented security layer that sits between AI agents and Model Context Protocol (MCP) tools. It tracks provenance across transformations and agents, reconstructs possible influence on sensitive tool arguments, and enforces risk-sensitive policies (**ALLOW** / **BLOCK** / **CONFIRM**).

This is **not** a prompt-injection classifier and **not** a keyword filter.

> **Current status:** Milestones **0–2** complete: assessment, provenance registry, and MCP security proxy with mock email. Next: deeper transform graph + reconstruction. See [docs/implementation_plan.md](docs/implementation_plan.md).

## Quick start

```bash
make install
make test
```

No API keys required. Packages: `agenttaint-core`, `agenttaint-provenance`, `agenttaint-risk`, `agenttaint-policy`, `agenttaint-audit`, `agenttaint-mcp-proxy`, plus `agenttaint-mock-email`.

See [docs/mcp_proxy.md](docs/mcp_proxy.md) for the enforcement boundary.

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
| [docs/security_policies.md](docs/security_policies.md) | Policy principles |
| [docs/mvp.md](docs/mvp.md) | Smallest hypothesis-testing slice |
| [docs/implementation_plan.md](docs/implementation_plan.md) | Ordered tasks + acceptance criteria |
| [docs/free_development_plan.md](docs/free_development_plan.md) | Local-first stack, hardware, licenses |
| [docs/benchmark_methodology.md](docs/benchmark_methodology.md) | Evaluation protocol |
| [docs/limitations.md](docs/limitations.md) | Honest limits |
| [docs/mcp_proxy.md](docs/mcp_proxy.md) | MCP proxy supported features & limits |
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
7. Dashboard  
8. Research release  

---

## License

Apache-2.0 (intended; `LICENSE` file added with first implementation milestone).
