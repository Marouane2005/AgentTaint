# AgentTaint Benchmark Report (`test`)

- **report_id:** `fdd975f9-1a3b-446f-b322-54271a2dd2f7`
- **created_at:** `2026-11-13T16:00:38.958613+00:00`
- **dataset_version:** `2026.11.13-m7.1`
- **seed:** `2120`
- **semantic_backend:** `fixture-hash-embedder-v1`
- **command:** `python -m agenttaint_benchmark experiment --split test --seed 2120 --seeds 2120,7,42,99,12345 --semantic-backend fixture --tag experiment_fixture`

## Per-defense metrics

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coarse_taint | 65 | 0.000 | 0.000 | 0.296 | 0.000 | 0.704 | n/a | n/a | n/a | 1.32 | 2.58 |
| combined:combined | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.974 | 0.987 | 6.62 | 10.23 |
| explicit_only | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 2.55 | 3.95 |
| reconstruction_only:combined | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.974 | 0.987 | 5.85 | 9.89 |
| undefended | 65 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 1.83 | 2.92 |

## Reconstruction ablations (`reconstruction_only`)

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lexical | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.974 | 0.987 | 5.33 | 7.79 |
| lexical_structural | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.974 | 0.987 | 5.45 | 7.95 |
| semantic | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.158 | 0.273 | 1.70 | 4.24 |
| structural | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.974 | 0.987 | 5.42 | 7.75 |

## Per-difficulty metrics (`combined`)

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hard | 23 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.951 | 0.975 | 7.30 | 10.96 |
| standard | 42 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5.52 | 9.47 |

## Per-family metrics (`combined`)

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adaptive_split | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 0.333 | 0.500 | 4.21 | 4.97 |
| ambiguous | 2 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 4.45 | 4.46 |
| benign_authorized | 6 | n/a | n/a | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 4.84 | 6.31 |
| benign_low_risk | 6 | n/a | n/a | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 1.67 | 2.65 |
| benign_overlap | 2 | n/a | n/a | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 6.96 | 6.96 |
| benign_similar | 2 | n/a | n/a | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 6.91 | 6.92 |
| conflicting | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4.96 | 5.09 |
| direct | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 4.65 | 4.72 |
| extracted | 2 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 6.77 | 6.92 |
| forged_metadata | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 4.43 | 4.52 |
| heavy_paraphrase | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 9.55 | 9.59 |
| memory | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5.60 | 5.75 |
| memory_poison | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 7.99 | 8.28 |
| missing_lineage | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 7.30 | 7.47 |
| multi_agent | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 9.58 | 9.78 |
| multi_hop | 4 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 10.92 | 11.03 |
| multi_source | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 6.84 | 6.89 |
| obfuscated | 2 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 4.47 | 4.51 |
| paraphrased | 4 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 7.19 | 9.87 |
| summarized | 3 | 0.000 | 0.000 | n/a | n/a | n/a | 1.000 | 1.000 | 1.000 | 7.01 | 7.26 |

## Multi-seed bootstrap variability

| defense | metric | mean | std | min | max | n_seeds |
| --- | --- | --- | --- | --- | --- | --- |
| undefended | asr | 1.000 | 0.000 | 1.000 | 1.000 | 5 |
| undefended | utility | 1.000 | 0.000 | 1.000 | 1.000 | 5 |
| undefended | fpr_block | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| undefended | fpr_confirm | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| undefended | provenance_f1 | n/a | n/a | n/a | n/a | 5 |
| undefended | latency_ms_median | 1.822 | 0.031 | 1.761 | 1.840 | 5 |
| coarse_taint | asr | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| coarse_taint | utility | 0.681 | 0.128 | 0.526 | 0.833 | 5 |
| coarse_taint | fpr_block | 0.319 | 0.128 | 0.167 | 0.474 | 5 |
| coarse_taint | fpr_confirm | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| coarse_taint | provenance_f1 | n/a | n/a | n/a | n/a | 5 |
| coarse_taint | latency_ms_median | 1.309 | 0.015 | 1.290 | 1.323 | 5 |
| explicit_only | asr | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| explicit_only | utility | 1.000 | 0.000 | 1.000 | 1.000 | 5 |
| explicit_only | fpr_block | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| explicit_only | fpr_confirm | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| explicit_only | provenance_f1 | n/a | n/a | n/a | n/a | 5 |
| explicit_only | latency_ms_median | 2.561 | 0.057 | 2.505 | 2.630 | 5 |
| reconstruction_only:combined | asr | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| reconstruction_only:combined | utility | 1.000 | 0.000 | 1.000 | 1.000 | 5 |
| reconstruction_only:combined | fpr_block | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| reconstruction_only:combined | fpr_confirm | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| reconstruction_only:combined | provenance_f1 | 0.981 | 0.009 | 0.971 | 0.993 | 5 |
| reconstruction_only:combined | latency_ms_median | 5.663 | 0.472 | 4.731 | 5.995 | 5 |
| combined:combined | asr | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| combined:combined | utility | 1.000 | 0.000 | 1.000 | 1.000 | 5 |
| combined:combined | fpr_block | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| combined:combined | fpr_confirm | 0.000 | 0.000 | 0.000 | 0.000 | 5 |
| combined:combined | provenance_f1 | 0.981 | 0.009 | 0.971 | 0.993 | 5 |
| combined:combined | latency_ms_median | 6.217 | 0.807 | 5.229 | 6.895 | 5 |

## Limitations (recorded with run)

- Custom synthetic scenarios — not a substitute for production agent telemetry.
- No head-to-head numbers vs CaMeL/FIDES/CapLite/NeuroTaint (not run here).
- CONFIRM is treated as non-success for ASR and non-completion for utility (no human in the loop during the batch run).
- Static recipient denylists are disabled in provenance baselines to isolate provenance mechanisms.
- Provenance P/R scored only for reconstruction-enabled defenses on attacks.
- Multi-seed variability uses bootstrap resampling of a fixed held-out corpus (evaluation is otherwise deterministic).
- Semantic backend for this experiment: fixture-hash-embedder-v1
- Bootstrap variability reflects sampling uncertainty on a fixed synthetic corpus, not stochastic model noise.

## Notes

- Full-corpus scenarios: 65
- Bootstrap seeds: [2120, 7, 42, 99, 12345]
