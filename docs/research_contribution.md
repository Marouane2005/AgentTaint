# Honest assessment of research contribution (post–Milestone 7)

**Date:** 2026-11-13  
**Evidence basis:** Custom synthetic benchmark `2026.11.13-m7.1` + adversarial unit tests + AgentDojo feasibility probe.  
**Rule:** Claims must be supported by measured artifacts in-repo.

---

## Defensible contribution (supported)

AgentTaint provides a **reproducible, free/local research platform** that:

1. Enforces tool calls at an **MCP security gateway** with risk-tiered decisions.  
2. Maintains an explicit **KNOWN / INFERRED / UNKNOWN / PARTIAL** provenance epistemology (INFERRED never silently becomes KNOWN or sole HIGH-risk authorization).  
3. Supports **authenticated cross-agent envelopes**, confirmation binding, and fail-closed HIGH-risk paths.  
4. Offers **ablation-ready reconstruction** (lexical / structural / optional local BGE semantic).  
5. Ships a **held-out custom multi-agent benchmark** with baselines, multi-seed bootstrap variability, and published raw reports.

On the expanded synthetic held-out set, provenance-aware defenses stopped auto-exfiltration (`ASR=0`) while preserving benign utility better than coarse taint (`utility≈0.70` coarse vs `1.0` provenance), with documented hard-case failures and BGE latency trade-offs.

## Not supported (do not claim)

- Real-world deployment effectiveness  
- Novelty as “first provenance system” (CaMeL/FIDES/CapLite/NeuroTaint already exist)  
- Superiority without a fair shared protocol against those systems  
- AgentDojo / InjecAgent competitive scores (not fully run under free/local constraints)  
- Calibrated P(causation) from reconstruction scores  

## Recommended paper framing

> An MCP-boundary information-flow enforcement layer with explicit epistemic provenance states and ablation-ready reconstruction, evaluated on a reproducible synthetic cross-agent suite under free/local constraints, with honest limits versus prior online defenses and offline semantic taint systems.

## Next evidence that would strengthen claims

1. Fair comparison harness against at least one prior system on a shared task suite.  
2. AgentDojo (or similar) with a declared local LLM configuration and published logs.  
3. Human confirmation studies (CONFIRM outcomes currently batch-treated as non-success).  
4. Larger adaptive/adversarial corpora where identifiers never appear in candidate text.
