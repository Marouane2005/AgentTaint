# AgentTaint research report

**Date:** 2026-11-18  
**Scope:** Milestones 0–14 on the free/local stack  
**Rule:** Every claim below is tied to in-repo artifacts. Unsupported claims are listed as such.

---

## 1. Problem

Tool-using agents can be steered by untrusted content (email, web, files) into
dangerous actions after summarization, paraphrase, memory, or cross-agent
delegation. Prompt classifiers alone do not preserve authority provenance at the
MCP tool boundary.

## 2. Approach

AgentTaint is an **online MCP-boundary enforcement layer**:

1. **Provenance registry** with epistemic states `KNOWN` / `INFERRED` /
   `UNKNOWN` / `PARTIAL` (INFERRED never silently becomes KNOWN).
2. **SecurityGateway** chokepoint: non-ALLOW never calls the tool backend.
3. **Reconstruction** with mandatory channel ablation (lexical, structural,
   semantic, explicit).
4. **Structured authorization grants** (not free-text USER scraping).
5. **Confirmation binding** with durable single-use consume + provenance-context
   hash.
6. **Per-agent envelope keys** for cooperating multi-agent transfer.

## 3. Evaluation evidence

| Evidence | Artifact | Result (honest) |
|----------|----------|-----------------|
| Held-out synthetic suite | `docs/benchmark_results_m13.md` | Provenance defenses ASR=0; undefended ASR=1.0; coarse utility≈0.70 |
| Channel ablations | same | Lexical/structural strong on this corpus; semantic-only weak under fixture; explicit-only recall 0 without parents |
| Adversarial units | `tests/unit/test_m13_adversarial_evaluation.py` (+ M9/M10/M11) | Forgery, races, bypass, homoglyph, missing lineage covered |
| Latency/memory | M13 report | Combined median ≈6–7 ms; process `ru_maxrss` ≈118–121 MiB (fixture) |
| External ASR | `docs/external_benchmarks_m12.md` | AgentDojo / InjecAgent **not evaluated** (LLM required) |

## 4. Related systems

CaMeL, FIDES, CapLite, and NeuroTaint address overlapping threats with different
placement (interpreter, middleware, write-grounding, offline audit). AgentTaint’s
differentiating *engineering* focus is MCP-boundary enforcement + epistemic
provenance + ablation-ready reconstruction. **No superiority claim** is made
without a shared protocol. See `docs/related_work.md`.

## 5. Limitations & security assumptions

See `docs/limitations.md`. Critical assumptions:

- Cooperating agents use the SDK / envelopes correctly.
- Mock backends are stand-ins; production tools need their own schemas/grants.
- Synthetic near-zero ASR does **not** transfer to production agents.
- Fixture embeddings are not calibrated production embeddings.
- Cedar remains deferred (`docs/cedar_deferred.md`).
- Control plane is local-trust unless `AGENTTAINT_API_AUTH=required`.

## 6. Completeness verdict

**Demo / research-portfolio ready:** yes — reproducible suite, adversarial tests,
MCP multi-process proxy, durable security state, dashboard, one-command demo.

**Production MCP security product:** not yet — external ASR unevaluated, Cedar
deferred, SSE/resources/prompts unsupported, human CONFIRM UX incomplete.

Recommended framing (unchanged in substance from M7/M9):

> An MCP-boundary information-flow enforcement layer with explicit epistemic
> provenance states and ablation-ready reconstruction, evaluated on a
> reproducible synthetic cross-agent suite under free/local constraints, with
> honest limits versus prior online defenses and offline semantic taint systems.
