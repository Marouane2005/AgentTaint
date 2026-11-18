# Honest assessment of research contribution (post–Milestone 14)

**Date:** 2026-11-18  
**Evidence basis:** Custom synthetic benchmark `2026.11.18-m12.1` + M13 ablations +
adversarial unit suites (M9–M13) + MCP multi-process tests + AgentDojo feasibility
probe.  
**Rule:** Claims must be supported by measured artifacts in-repo.

---

## Defensible contribution (supported)

AgentTaint provides a **reproducible, free/local research platform** that:

1. Enforces tool calls at an **MCP security gateway** with risk-tiered decisions.  
2. Maintains an explicit **KNOWN / INFERRED / UNKNOWN / PARTIAL** provenance epistemology (INFERRED never silently becomes KNOWN or sole HIGH-risk authorization).  
3. Supports **per-agent authenticated envelopes**, confirmation binding, durable single-use consume, and fail-closed HIGH-risk paths.  
4. Offers **ablation-ready reconstruction** (lexical / structural / explicit / optional local BGE semantic).  
5. Ships a **held-out custom multi-agent benchmark** with baselines, channel ablations, multi-seed bootstrap variability, and published markdown summaries.  
6. Includes a **local control-plane dashboard** that never invents gateway decisions.

On the held-out synthetic set (M13 fixture run), provenance-aware defenses stopped
auto-exfiltration (`ASR=0`) while preserving benign utility better than coarse
taint (`utility≈0.70` coarse vs `1.0` provenance), with documented hard-case and
channel-ablation limits.

## Not supported (do not claim)

- Real-world deployment effectiveness  
- Novelty as “first provenance system” (CaMeL/FIDES/CapLite/NeuroTaint already exist)  
- Superiority without a fair shared protocol against those systems  
- AgentDojo / InjecAgent competitive scores (not run under free/local constraints)  
- Calibrated P(causation) from reconstruction scores  
- Production completeness (Cedar deferred; SSE/resources/prompts unsupported)

## Recommended paper framing

> An MCP-boundary information-flow enforcement layer with explicit epistemic provenance states and ablation-ready reconstruction, evaluated on a reproducible synthetic cross-agent suite under free/local constraints, with honest limits versus prior online defenses and offline semantic taint systems.

## Completeness

| Bar | Met? |
|-----|------|
| Demo / portfolio research release | **Yes** (with documented limits) |
| Production MCP security product | **No** |

## Next evidence that would strengthen claims

1. Fair comparison harness against at least one prior system on a shared task suite.  
2. AgentDojo (or similar) with a declared local LLM configuration and published logs.  
3. Human confirmation studies (CONFIRM outcomes currently batch-treated as non-success).  
4. Larger adaptive/adversarial corpora where identifiers never appear in candidate text.
