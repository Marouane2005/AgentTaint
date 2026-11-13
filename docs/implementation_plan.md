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

## Milestone 4 — Reconstruction (Week 4)

| ID | Task | Acceptance |
|----|------|------------|
| 4.1 | Lexical matcher | Ablation flag `lexical` |
| 4.2 | Structural extractor | Email/URL/path normalization tests + Unicode cases |
| 4.3 | Semantic matcher (optional extra) | Skips if model missing; cosine tests with fixture vectors |
| 4.4 | Evidence aggregation | Per-argument ArgumentEvidence; no silent promotion |
| 4.5 | Ablation harness | Same scenario runnable under each channel |

**Deliverable:** Reconstruction engine with ablation.

---

## Milestone 5 — SDK, cross-agent, policy, confirm (Week 5)

| ID | Task | Acceptance |
|----|------|------------|
| 5.1 | Agent SDK context | summarize/delegate/accept |
| 5.2 | Envelope HMAC / shared-secret verify | Tamper rejected |
| 5.3 | Memory store with provenance | remember/recall edges |
| 5.4 | Risk classifier config | email.send=HIGH, email.read=LOW |
| 5.5 | PolicyAdapter + YAML policies | Scenario demo BLOCK/ALLOW/CONFIRM |
| 5.6 | CLI confirmation | Bound to args hash; replay fails |
| 5.7 | Fail-closed when store down | HIGH-risk blocked |
| 5.8 | Cedar backend (stretch) | Same tests via Cedar **or** explicitly deferred |

**Deliverable:** Cross-agent provenance-aware enforcement.

---

## Milestone 6 — Custom benchmark + baselines (Week 6)

| ID | Task | Acceptance |
|----|------|------------|
| 6.1 | Scenario schema + generator (separate from eval) | Fixed seeds; no leakage docs |
| 6.2 | Baselines: undefended, coarse taint, explicit-only, reconstruct-only | Runnable |
| 6.3 | Metrics writer → `benchmarks/reports/` | JSON schema validated |
| 6.4 | AgentDojo adapter (best effort) | Document works / partial / blocked |
| 6.5 | InjecAgent adapter (best effort) | Same honesty |

**Deliverable:** Reproducible experiments (custom required; externals as available).

---

## Milestone 7 — Dashboard + hardening (Week 7)

| ID | Task | Acceptance |
|----|------|------------|
| 7.1 | FastAPI metrics + graph export | Used by UI |
| 7.2 | Next.js overview + timeline + decision explorer | Live data only |
| 7.3 | Graph explorer | KNOWN/INFERRED/UNKNOWN visual distinction |
| 7.4 | Security tests pack | Forgery, replay, bypass attempts |
| 7.5 | Playwright smoke | Dashboard loads decisions |

**Deliverable:** Developer-facing platform over real engine.

---

## Milestone 8 — Research release (Week 8)

| ID | Task | Acceptance |
|----|------|------------|
| 8.1 | `docs/limitations.md` + paper draft | No invented numbers/citations |
| 8.2 | Docker Compose full stack | Fresh clone demo |
| 8.3 | Demo recording script | Walkthrough artifact |
| 8.4 | CONTRIBUTING + LICENSE | Present |
| 8.5 | Related work update after results | Novelty claim only if supported |

---

## Immediate next coding tasks (after this assessment merges/lands)

1. Create `packages/core` + `packages/provenance`  
2. SQLite registry + unit tests  
3. Trust registry + source labeler  
4. Research log entry for first implementation decisions  

Order is strict: **registry before proxy before reconstruction before dashboard**.
