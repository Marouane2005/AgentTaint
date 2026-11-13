# Benchmark validity assessment (M9)

**Scope:** Review M6/M7 methodology and **saved** artifacts under `benchmarks/reports/`.  
**Rule:** Existing result files are preserved; this document does not overwrite them.

## Separation of claims

| Layer | What M6/M7 measure | What they do **not** measure |
|-------|--------------------|------------------------------|
| Synthetic custom suite | Policy + reconstruction behavior on authored scenarios | Production agent frameworks |
| Reconstruction quality | Ablation ASR/utility/provenance F1 under fixture/BGE | Causal probability |
| End-to-end agent security | Not evaluated on AgentDojo/InjecAgent | — |
| Real-world | Not evaluated | — |

**Do not describe near-zero ASR on the synthetic suite as proof of general attack prevention.**

## Checks

### Dataset separation
- Held-out `test` split used for reported tables (`split: test` in saved JSON).
- Generator scripts live under `packages/benchmark`; scenarios are fixed dataset versions (`2026.11.13-m7.1` for M7 reports).
- **Valid:** train/dev vs test separation exists in the methodology.  
- **Caveat:** scenarios are synthetic and often expose contiguous structural identifiers — high structural hit rates inflate reconstruction wins.

### Generator / evaluator independence
- Defense evaluation uses the same deterministic environment and formal decision outcomes (ALLOW/BLOCK/CONFIRM), not an LLM-as-judge.
- **Valid** for this custom suite.  
- **Not comparable** to AgentDojo’s environment-state checks without an adapter.

### Reproducibility
- Saved reports include `seed`, `dataset_version`, `semantic_backend`, `per_defense`, `per_ablation`, `limitations`.
- Commands: `make benchmark`, `make benchmark-bge`, `make benchmark-experiment`.
- **Assessment:** Fixture backend runs are independently reproducible on a clean install. BGE runs require local model download and are heavier but were previously executed and saved (`report_test_bge_*.json`).

### Baseline fairness
- Baselines include `undefended`, `coarse_taint`, `explicit_only`, reconstruction-only, and combined.
- Static recipient denylists are disabled in methodology to isolate provenance mechanisms (recorded in report limitations).
- **Fair within the custom suite.** Not a fair comparison to CaMeL/FIDES/CapLite/NeuroTaint without a shared protocol.

### Metric definitions
- ASR: attack success (CONFIRM treated as non-success for ASR in recorded limitations).
- Utility / FPR_block / provenance F1 / latency medians present in reports.
- **Clear in docs;** CONFIRM-as-non-success must stay explicit when quoting ASR.

### Bootstrap methodology
- Multi-seed experiment artifacts (`variability_fixture.json`, `report_test_experiment_fixture_*`) quantify **sampling uncertainty on a fixed synthetic set**, not stochastic LLM variance.
- Correctly scoped in M7 docs; M9 affirms that wording.

### Threshold selection
- Reconstruction support thresholds were not retuned on the held-out test for M9.
- Fixture embedder is a hash-based stand-in — semantic ablation numbers are **not** calibrated production embeddings.

### Hard-case coverage
- M7 adds multi-hop, memory, forged metadata, adaptive splits.
- Adaptive splits can still evade fixture reconstruction (documented).

## Independent reproduction note (M9)

Inspected on-disk without modification:

- `benchmarks/reports/report_test_fixture_72370391.json` — dataset `2026.11.13-m7.1`, seed `2120`, defenses present, limitations listed.
- `benchmarks/reports/report_test_bge_512a53ec.json` — separate BGE tag preserved.
- `benchmarks/reports/report_test_experiment_fixture_fdd975f9.json` — multi-seed experiment preserved.
- `benchmarks/reports/agentdojo_probe.json` — install/suite probe only; **no ASR**.

## Conclusion

M6/M7 results are **internally coherent synthetic evidence**. They support research discussion of provenance-aware enforcement under instrumentation assumptions. They do **not** authorize real-world security claims or external-benchmark leaderboard placement.
