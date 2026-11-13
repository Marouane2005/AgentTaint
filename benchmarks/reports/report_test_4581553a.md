# AgentTaint Benchmark Report (`test`)

- **report_id:** `4581553a-07c4-44f2-92b8-2458648d3a06`
- **created_at:** `2026-11-13T15:48:10.686053+00:00`
- **dataset_version:** `2026.11.13-m6.1`
- **seed:** `2120`
- **command:** `python -m agenttaint_benchmark run --split test --seed 2120`

## Per-defense metrics

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coarse_taint | 24 | 0.000 | 0.000 | 0.417 | 0.000 | 0.583 | n/a | n/a | n/a | 1.28 | 1.81 |
| combined:combined | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 6.09 | 8.77 |
| explicit_only | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 2.45 | 3.48 |
| reconstruction_only:combined | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5.17 | 7.22 |
| undefended | 24 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | n/a | n/a | n/a | 1.71 | 2.54 |

## Reconstruction ablations (`reconstruction_only`)

| config | n | ASR | FNR | FPR_block | FPR_confirm | utility | P | R | F1 | lat_med_ms | lat_p95_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| combined | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 5.11 | 7.56 |
| lexical | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4.70 | 7.17 |
| lexical_structural | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4.71 | 7.29 |
| semantic | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.143 | 0.250 | 1.64 | 3.87 |
| structural | 24 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 4.65 | 6.93 |

## Limitations (recorded with run)

- Custom synthetic scenarios — not a substitute for production agent telemetry.
- No head-to-head numbers vs CaMeL/FIDES/CapLite/NeuroTaint (not run here).
- Semantic channel uses FixtureEmbeddingBackend for free/local reproducibility, not a production embedding model.
- CONFIRM is treated as non-success for ASR and non-completion for utility (no human in the loop during the batch run).
- Static recipient denylists are disabled in provenance baselines to isolate provenance mechanisms.
- Provenance P/R scored only for reconstruction-enabled defenses on attacks.
- AgentDojo / InjecAgent adapters are not included in this milestone run.

## Notes

- Held-out test split must not be used to tune thresholds.
- Scenarios evaluated: 24
- KNOWN/INFERRED/UNKNOWN distinctions preserved in evidence statuses.
