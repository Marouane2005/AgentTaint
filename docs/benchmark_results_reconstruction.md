# Reconstruction value: explicit lineage vs reconstruction

Produced by `scripts/run_reconstruction_eval.py` (deterministic, no LLM). Columns:

- **ASR**: attacks ALLOWed (CONFIRM counts as stopped).
- **attack BLOCK**: attacks stopped outright, without relying on a reviewer.
- **ASR if CONFIRM approved**: attacks that would execute if a permissive reviewer approved every confirmation (ALLOW or CONFIRM).
- **benign BLOCK**: false-positive blocks on benign scenarios.
- **utility if CONFIRM approved**: benign scenarios not BLOCKed.

## split `test` (2026.11.18-m12.1), embedder `fixture` — 41 attacks / 27 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.442 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 0.296 | 0.704 | 0.704 | n/a | n/a | n/a | 1.587 |
| explicit_only | 0.000 | 0.805 | 0.195 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.928 |
| reconstruction_only | 0.000 | 0.951 | 0.049 | 0.000 | 1.000 | 1.000 | 1.000 | 0.976 | 0.988 | 8.758 |
| combined | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.976 | 0.988 | 8.255 |

## split `reconstruction` (2026.11.18-rec.1), embedder `fixture` — 16 attacks / 8 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.682 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1.701 |
| explicit_only | 0.000 | 0.000 | 1.000 | 0.000 | 0.250 | 1.000 | n/a | n/a | n/a | 3.662 |
| reconstruction_only | 0.000 | 0.875 | 0.125 | 0.000 | 0.250 | 1.000 | 0.467 | 0.875 | 0.609 | 8.747 |
| combined | 0.000 | 0.875 | 0.125 | 0.000 | 0.250 | 1.000 | 0.467 | 0.875 | 0.609 | 9.252 |

## split `test` (2026.11.18-m12.1), embedder `bge` — 41 attacks / 27 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.531 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 0.296 | 0.704 | 0.704 | n/a | n/a | n/a | 1.668 |
| explicit_only | 0.000 | 0.805 | 0.195 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.978 |
| reconstruction_only | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 96.229 |
| combined | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 91.174 |

## split `reconstruction` (2026.11.18-rec.1), embedder `bge` — 16 attacks / 8 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 3.614 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1.652 |
| explicit_only | 0.000 | 0.000 | 1.000 | 0.000 | 0.250 | 1.000 | n/a | n/a | n/a | 3.536 |
| reconstruction_only | 0.000 | 1.000 | 0.000 | 0.000 | 0.250 | 1.000 | 0.500 | 1.000 | 0.667 | 121.373 |
| combined | 0.000 | 1.000 | 0.000 | 0.000 | 0.250 | 1.000 | 0.500 | 1.000 | 0.667 | 92.227 |

## Interpretation

- Strict ASR is 0.000 for every provenance defense because HIGH sinks without a
  structured grant never ALLOW; it cannot separate explicit lineage from
  reconstruction. The reviewer-sensitivity columns can.
- **Held-out test split:** explicit lineage alone BLOCKs 80.5% of attacks and
  leaves 19.5% to a human reviewer (missing or forged lineage → CONFIRM).
  Combined AgentTaint BLOCKs 100% with no benign false blocks.
- **Reconstruction split (broken USER-only lineage):** explicit lineage BLOCKs
  none of the 16 attacks. With the fixture embedder, reconstruction BLOCKs 14/16
  (13/16 before the 2026-11 hardening; the extra one is an address spelled out in
  prose) with 0/8 benign false blocks. With BAAI/bge-small-en-v1.5 on CPU it BLOCKs
  16/16 and, since semantic similarity alone can no longer promote structured
  arguments, falsely BLOCKs 0/8 benign controls (3/8 before the hardening).
- The cost is latency: with BGE, the median combined decision on the test split went
  from about 39 ms to about 91 ms on the same CPU, because session reconstruction now
  always runs for MEDIUM and HIGH calls. See
  [benchmark_results_hardening.md](benchmark_results_hardening.md).
- Synthetic scenarios only; these numbers say nothing about production traffic.
