# AgentTaint research report

**Date:** 2026-11-18  
**Scope:** Milestones 0–14 on the free/local stack  
**Rule:** Every claim below is tied to in-repo artifacts. Unsupported claims are listed as such.

The full write-up (design, evaluation, related work, references) is
[technical_report.md](technical_report.md); this page is the short summary.

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
| Reconstruction value | `docs/benchmark_results_reconstruction.md` | Broken-lineage split: explicit lineage BLOCKs 0/16 attacks, combined 13/16 (fixture, 0 benign false blocks) or 16/16 (BGE, 3/8 benign false blocks) |
| Adversarial units | `tests/unit/test_m13_adversarial_evaluation.py` (+ M9/M10/M11) | Forgery, races, bypass, homoglyph, missing lineage covered |
| Latency/memory | M13 report | Combined median ≈6–7 ms; process `ru_maxrss` ≈118–121 MiB (fixture) |
| External ASR | `docs/external_results_agentdojo.md` | AgentDojo sampled subset, `mercury-3`: tool-action ASR 0 with and without AgentTaint (model resisted); utility 0.85 → 0.35 (strict) / 0.50 (approve). InjecAgent not run |

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
- Cedar is the default policy engine; it decides from Python-computed facts (`docs/cedar_policy.md`).
- Control plane is local-trust unless `AGENTTAINT_API_AUTH=required`.

## 5b. M15 confirmation hardening

Fixes from the post-M14 security probes:

| Probe | M14 | M15 |
|-------|-----|-----|
| Agent approves its own CONFIRM over MCP, then retries | ALLOW (email sent) | No approval tool; retry stays BLOCK until a human approves via CLI/API |
| Caller-supplied `agent_id` / provenance hash | Trusted | Rejected / ignored |
| Default confirmation secret | Hard-coded | None; proxy refuses to start |
| `http.get` exfiltration with no declared parents after an untrusted read | ALLOW | CONFIRM (BLOCK with `fail_closed_unknown_medium`) |
| Shell container limits | no network, read-only rootfs, no-new-privileges | + memory, CPU, pids, cap-drop ALL, nobody user, kill timeout |

Benchmark numbers on the 68-scenario test split are unchanged (the suite has no
MEDIUM sinks). See `docs/limitations.md` items 40–46.

## 6. Completeness verdict

**Demo / research-portfolio ready:** yes — reproducible suite, adversarial tests,
MCP multi-process proxy, durable security state, dashboard, one-command demo.

**Production MCP security product:** not yet — external evaluation is a small
sampled subset, utility cost on data-dependent tasks is high, SSE/resources/prompts
are unsupported. Human CONFIRM approval is available via CLI, API and the
dashboard approval screen (dedicated approver token).

Recommended framing (unchanged in substance from M7/M9):

> An MCP-boundary information-flow enforcement layer with explicit epistemic
> provenance states and ablation-ready reconstruction, evaluated on a
> reproducible synthetic cross-agent suite under free/local constraints, with
> honest limits versus prior online defenses and offline semantic taint systems.
