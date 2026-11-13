# Benchmark Methodology

**Status:** Implemented (Milestones 6–7); validity reassessed in M9  
**Rule:** Never invent results. Empty / missing reports mean “not run.”  
**Current dataset:** `2026.11.13-m7.1`  
**M9:** See `docs/benchmark_validity_m9.md` — do not overwrite saved `benchmarks/reports/*`.

---

## Custom cross-agent transformation benchmark (primary)

### Dataset

| Split | File | Role |
|-------|------|------|
| train | `benchmarks/data/scenarios_train.json` | Development-similar patterns |
| dev | `benchmarks/data/scenarios_dev.json` | Smoke / design checks |
| test | `benchmarks/data/scenarios_test.json` | **Held-out** evaluation |
| challenge | `benchmarks/data/scenarios_challenge.json` | Expected-failure probes (not in aggregates) |

- **Version file:** `benchmarks/data/VERSION`  
- **Generator (≠ evaluator):** `scripts/generate_benchmark_scenarios.py` + `scripts/m7_scenario_bank.py` (seed `2120`)  
- Held-out recipients avoid unit-test fixtures (`attacker@example.com`, `bob@corp.example`)  
- M7 hard families: `heavy_paraphrase`, `multi_hop`, `memory_poison`, `forged_metadata`, `ambiguous`, harder `adaptive_split`  
- Semantic backends: `--semantic-backend fixture|bge|none` (BGE = local `BAAI/bge-small-en-v1.5`)  
- Multi-seed: `python -m agenttaint_benchmark experiment --seeds ...` (bootstrap on fixed corpus)

### Scenario families

1. Direct malicious instruction in tool output  
2. Summarized malicious instruction  
3. Paraphrased instruction  
4. Extracted email/URL only  
5. Memory store → recall → sink  
6. Multi-agent delegation  
7. Multiple untrusted sources  
8. Conflicting USER vs UNTRUSTED  
9. Missing provenance metadata (gaps)  
10. Obfuscated identifiers  
11. Adaptive / split identity  
12. Benign authorized / overlap / similar / low-risk

### Protocol

- Fixed RNG seed recorded in every report JSON.  
- Hold out `test` unused for threshold/policy tuning.  
- Record defense config + ablation mode in each report.  
- Static denylists disabled for provenance baselines.  
- Semantic ablation uses `FixtureEmbeddingBackend` unless otherwise stated.

### Metrics

| Metric | Definition |
|--------|------------|
| ASR | `# attack ALLOW / # attack` |
| FNR | Same as ASR for this binary sink setup |
| FPR_block | `# benign BLOCK / # benign` |
| FPR_confirm | `# benign CONFIRM / # benign` |
| Utility | `# benign ALLOW / # benign` |
| Provenance P/R/F1 | Over reconstruction matches vs gold untrusted sources (attacks only) |
| Latency | per-scenario wall ms; report median + p95 |
| Resources | `resource.getrusage` RSS + user CPU for the process |

`CONFIRM` is **not** attack success and **not** benign completion (no human in batch loop).

### Baselines

1. Undefended (`AllowAllPolicy`)  
2. Coarse taint (any session UNTRUSTED/UNKNOWN → BLOCK HIGH)  
3. Explicit lineage only  
4. Reconstruction only (+ channel ablations)  
5. Combined AgentTaint  

Label these as AgentTaint configurations / coarse reimplementations — **not** CaMeL/FIDES/CapLite/NeuroTaint.

---

## AgentDojo / InjecAgent

**Status (M7):** AgentDojo installable; suites `banking/slack/travel/workspace` (v1.2.2) listable. Full LLM-backed evaluation **not executed** under free/local constraints. Probe artifact: `benchmarks/reports/agentdojo_probe.json`.  
InjecAgent: not integrated. Do not substitute custom numbers for those benchmarks.

---

## Results

- M6 baseline write-up: [benchmark_results.md](benchmark_results.md)  
- M7 expansion / BGE / variability / contribution: [benchmark_results_m7.md](benchmark_results_m7.md), [research_contribution.md](research_contribution.md)
