# Implementation Plan — Ordered Tasks & Acceptance Criteria

**Status:** Research assessment complete → implementation begins at Milestone 0  
**Date:** 2026-11-13

Each task is done only when its **acceptance tests** pass.

---

## Milestone 0 — Assessment (this PR)

- [x] Literature review (`docs/related_work.md`)
- [x] Threat model (`docs/threat_model.md`)
- [x] Feasibility (`docs/feasibility.md`)
- [x] Architecture (`docs/architecture.md`)
- [x] Free stack plan (`docs/free_development_plan.md`)
- [x] MVP definition (`docs/mvp.md`)
- [x] This plan + research log bootstrap

**Accept:** Documents committed; no code claims beyond assessment.

---

## Milestone 1 — Provenance foundation (Week 1)

| ID | Task | Acceptance |
|----|------|------------|
| 1.1 | Repo layout + `pyproject.toml` workspace | `pip install -e packages/core` works |
| 1.2 | Pydantic schemas: Origin, ProvenanceSpan, edges | Schema unit tests; version field present |
| 1.3 | Content hashing + redaction helpers | Stable sha256; redaction strips emails optionally |
| 1.4 | SQLite store via SQLAlchemy | CRUD spans/edges; migrations or `create_all` documented |
| 1.5 | Source labeler + trust registry YAML | Gmail-like tool → UNTRUSTED result origin |
| 1.6 | NetworkX graph wrapper over store | Ancestors/descendants tests; multi-parent |
| 1.7 | Unit tests + Ruff | `pytest tests/unit` green |

**Deliverable:** Working provenance registry.

---

## Milestone 2 — MCP proxy + mocks (Week 2) — DONE

| ID | Task | Acceptance |
|----|------|------------|
| 2.1 | Mock email MCP server | read/send against fixtures |
| 2.2 | Proxy lists tools from backend | MCP client sees tools |
| 2.3 | Intercept `tools/call` | Arguments captured; decision recorded |
| 2.4 | Label tool results as spans | `email.read` creates UNTRUSTED span |
| 2.5 | Stub policy allow-all except denylist | Forced block tool works |
| 2.6 | Integration tests proxy↔mock | No host email/network required |

**Deliverable:** Functioning MCP security boundary (minimal policy).  
**Evidence:** `docs/mcp_proxy.md`; unit + integration tests (gateway never forwards BLOCK).

---

## Milestone 3 — Graph completeness + transforms (Week 3) — DONE

| ID | Task | Acceptance |
|----|------|------------|
| 3.1 | TransformationRecord API | Summarize links parents→child |
| 3.2 | PARTIAL gap markers | Untracked transform creates gap |
| 3.3 | Graph integrity validation | Cycle detection / missing parent errors |
| 3.4 | Audit package for decisions | ToolCallDecision persisted (M2) |

**Also delivered:** multi-agent `transfer_to_agent`, memory store/retrieve, lineage completeness + origin conflict reports, inferred-link hook for reconstruction, tests for gaps/conflicts/chains.

**Deliverable:** Information-flow graph with transforms.

---

## Milestone 4 — Reconstruction (Week 4) — DONE

| ID | Task | Acceptance |
|----|------|------------|
| 4.1 | Lexical matcher | Ablation flag `lexical` |
| 4.2 | Structural extractor | Email/URL/path normalization tests + Unicode cases |
| 4.3 | Semantic matcher (optional extra) | Skips if model missing; cosine tests with fixture vectors |
| 4.4 | Evidence aggregation | Per-argument ArgumentEvidence; no silent promotion |
| 4.5 | Ablation harness | Same scenario runnable under each channel |

**Deliverable:** Reconstruction engine with ablation. See `docs/reconstruction.md`.

---

## Milestone 5 — SDK, cross-agent, policy, confirm (Week 5) — DONE

| ID | Task | Acceptance |
|----|------|------------|
| 5.1 | Agent SDK context | summarize/delegate/accept |
| 5.2 | Envelope HMAC / shared-secret verify | Tamper rejected |
| 5.3 | Memory store with provenance | remember/recall edges |
| 5.4 | Risk classifier config | email.send=HIGH, email.read=LOW |
| 5.5 | ProvenanceAwarePolicy + YAML | BLOCK/ALLOW/CONFIRM scenarios |
| 5.6 | CLI confirmation | Bound to args hash; replay fails |
| 5.7 | Fail-closed when registry unavailable | HIGH-risk blocked |
| 5.8 | Cedar backend (stretch) | **Explicitly deferred** |

**Also delivered:** confirmation binding (expiry/replay/arg mutation); reconstruction wired into `PolicyContext`; adversarial tests (forged/replayed envelopes, expired confirmations, post-approval arg change, conflicting provenance); `docs/security_integration.md`.

**Deliverable:** Cross-agent provenance-aware enforcement.  
**Hold:** Do not start Milestone 6 benchmarks until explicit approval.

---

## Milestone 6 — Custom benchmark + baselines (Week 6) — DONE

| ID | Task | Acceptance |
|----|------|------------|
| 6.1 | Scenario schema + generator (separate from eval) | Fixed seeds; held-out docs |
| 6.2 | Baselines: undefended, coarse, explicit, reconstruct, combined | Runnable |
| 6.3 | Metrics writer → `benchmarks/reports/` | JSON + MD reports |
| 6.4 | AgentDojo adapter (best effort) | **Not integrated — documented** |
| 6.5 | InjecAgent adapter (best effort) | **Not integrated — documented** |

**Also delivered:** channel ablations; challenge probes; `docs/benchmark_results.md` with measured tables.

**Deliverable:** Reproducible custom experiments. Externals unavailable this milestone.

---

## Milestone 7 — Research validation & benchmark expansion — DONE

*(User-directed: strengthen experimental evidence **before** dashboard.)*

| ID | Task | Acceptance |
|----|------|------------|
| 7.1 | Expand held-out corpus + hard families | Dataset `m7.1`; train/test separated |
| 7.2 | Local BGE vs fixture semantic eval | Separate measured reports |
| 7.3 | Multi-seed bootstrap variability | Seeds recorded; mean/std tables |
| 7.4 | Latency / utility / security trade-offs | Documented from actual runs |
| 7.5 | AgentDojo feasibility | Probe JSON; partial coverage only |
| 7.6 | Honest contribution assessment | `docs/research_contribution.md` |

**Deliverable:** Stronger reproducible evidence; **no dashboard**.  
**Hold:** Do not start dashboard / next milestone until explicit approval.

---

## Milestone 8 — Interactive Security Dashboard (complete)

| ID | Task | Acceptance |
|----|------|------------|
| 8.1 | FastAPI control plane (`agenttaint-api`) | Overview, graph, reconstruction, decisions, benchmarks, demo seed |
| 8.2 | Next.js dashboard sections | Overview, Provenance, Reconstruction, Gateway, Benchmark Lab |
| 8.3 | Interactive provenance graph | KNOWN / INFERRED / UNKNOWN / PARTIAL; dashed INFERRED edges |
| 8.4 | API + frontend tests | `tests/unit/test_api_dashboard.py`, Vitest ProvenanceGraph |
| 8.5 | Docs | `docs/dashboard.md` + README setup |

**Deliverable:** Developer-facing platform over real engine; demo seed labeled SIMULATED; gateway not bypassed.  
**Hold:** Do not start Milestone 9 until explicit approval.

---

## Milestone 9 — Research readiness & independent validation (complete on branch)

| ID | Task | Acceptance |
|----|------|------------|
| 9.1 | Independent architecture audit | `docs/m9_independent_review.md` with severity-rated findings |
| 9.2 | Adversarial regression suite | `tests/unit/test_m9_adversarial_guarantees.py` (scenarios 1–14) |
| 9.3 | Benchmark validity reassessment | `docs/benchmark_validity_m9.md` (no overwrite of reports) |
| 9.4 | External benchmark feasibility | `docs/external_benchmarks_feasibility.md` — AgentDojo/InjecAgent not evaluated |
| 9.5 | MCP compatibility assessment | `docs/mcp_compatibility_m9.md` |
| 9.6 | Correctness fixes from audit | Default provenance policy; audit confirmation_id; no provenance rewrite; nested redaction |

**Hold:** Public “production MCP security” claims remain blocked until MCP wire hooks + durable stores + external eval (or explicit not-evaluated labeling) are settled.  
**Verdict:** See M9 report — **B** (demo/portfolio ready; more engineering for production claims).

---

## Milestone 10 — MCP protocol & enforcement hardening (this branch)

| ID | Task | Acceptance |
|----|------|------------|
| 10.1 | CI + determinism | GitHub Actions pytest/ruff/mypy/dashboard; FixtureEmbeddingBackend sha256 |
| 10.2 | Structured authorization grants | No USER free-text scraping; session/agent/tool/arg scoped |
| 10.3 | MEDIUM sink untrusted influence | http.get / filesystem.write CONFIRM|BLOCK under untrusted parents/content |
| 10.4 | MCP `_agenttaint` wire | confirmation / parents / candidates; approve tool |
| 10.5 | Multi-process protocol proxy | Official MCP client+server over stdio; mock fs/http/shell |
| 10.6 | Durable nonce/confirmation + registry probe | Atomic consume; health `SELECT 1` |

**Hold:** Do not merge without review. Per-agent envelope keys, control-plane auth, Cedar, Postgres driver, and external ASR remain later milestones.

---

## Milestone 13 — Security & performance evaluation

| ID | Task | Acceptance |
|----|------|------------|
| 13.1 | Adversarial suite | Forgery, races, bypass, normalization, missing lineage, conflict, FP, exhaustion, latency |
| 13.2 | Channel ablations | lexical / structural / semantic / lexical_structural / explicit (+ combined) |
| 13.3 | Measured reports | `docs/benchmark_results_m13.md` additive; raw JSON gitignored under `benchmarks/reports/` |
| 13.4 | Repro harness | `scripts/run_m13_evaluation.py` |

**Hold:** Do not treat zero synthetic ASR as general attack prevention. External ASR still not evaluated.

---

## Milestone 14 — Research & public release

| ID | Task | Acceptance |
|----|------|------------|
| 14.1 | Research report + contribution honesty | `docs/research_report.md`, updated contribution/limitations |
| 14.2 | Install + one-command demo | `docs/install.md`, `make demo`, Compose `--profile demo` |
| 14.3 | README / architecture refresh | Professional entrypoint; M10–M14 notes |
| 14.4 | Dashboard polish | Research console framing; screenshots under `docs/screenshots/` |

**Hold:** Stop for merge approval before landing stacked PRs. Do not claim production completeness.

---

## Milestone 15 — Confirmation hardening

| ID | Task | Acceptance |
|----|------|------------|
| 15.1 | No self-approval | No approval tool on the agent MCP surface; out-of-band CLI + token-gated API; regression test must BLOCK |
| 15.2 | Fixed agent identity | Identity from proxy config; caller `agent_id` rejected; context hash server-side |
| 15.3 | No default secret | Proxy fails closed without `AGENTTAINT_CONFIRM_SECRET`; backend env stripped of secrets |
| 15.4 | MEDIUM undeclared lineage | Missing lineage = UNKNOWN; session-corpus reconstruction; CONFIRM/BLOCK by policy |
| 15.5 | Shell sandbox limits | memory/cpus/pids/cap-drop/user/timeout with command-line tests |
| 15.6 | Docs | Remove overclaims (M10 approve tool, M12 divergence, README sandbox); limitations updated |

---

## Immediate next coding tasks

1. Stop for merge approval on stacked PRs (M10→M14)  
2. Optional history rewrite of pre-M10 authorship (separate, after M14)
