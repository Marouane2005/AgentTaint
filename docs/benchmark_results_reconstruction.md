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
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 1.850 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 0.296 | 0.704 | 0.704 | n/a | n/a | n/a | 1.453 |
| explicit_only | 0.000 | 0.805 | 0.195 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 2.675 |
| reconstruction_only | 0.000 | 0.951 | 0.049 | 0.000 | 1.000 | 1.000 | 1.000 | 0.976 | 0.988 | 5.822 |
| combined | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.976 | 0.988 | 6.525 |

## split `reconstruction` (2026.11.18-rec.1), embedder `fixture` — 16 attacks / 8 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 1.852 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1.359 |
| explicit_only | 0.000 | 0.000 | 1.000 | 0.000 | 0.250 | 1.000 | n/a | n/a | n/a | 2.950 |
| reconstruction_only | 0.000 | 0.812 | 0.188 | 0.000 | 0.250 | 1.000 | 0.448 | 0.812 | 0.578 | 6.064 |
| combined | 0.000 | 0.812 | 0.188 | 0.000 | 0.250 | 1.000 | 0.448 | 0.812 | 0.578 | 7.096 |

## split `test` (2026.11.18-m12.1), embedder `bge` — 41 attacks / 27 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 1.828 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 0.296 | 0.704 | 0.704 | n/a | n/a | n/a | 1.438 |
| explicit_only | 0.000 | 0.805 | 0.195 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 2.796 |
| reconstruction_only | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.988 | 1.000 | 0.994 | 27.098 |
| combined | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.988 | 1.000 | 0.994 | 26.798 |

## split `reconstruction` (2026.11.18-rec.1), embedder `bge` — 16 attacks / 8 benign

| defense | ASR | attack BLOCK | ASR if CONFIRM approved | benign BLOCK | utility | utility if CONFIRM approved | P | R | F1 | median ms |
|---|---|---|---|---|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | n/a | n/a | n/a | 1.918 |
| coarse_taint | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1.457 |
| explicit_only | 0.000 | 0.000 | 1.000 | 0.000 | 0.250 | 1.000 | n/a | n/a | n/a | 3.073 |
| reconstruction_only | 0.000 | 1.000 | 0.000 | 0.375 | 0.250 | 0.625 | 0.432 | 1.000 | 0.604 | 38.008 |
| combined | 0.000 | 1.000 | 0.000 | 0.375 | 0.250 | 0.625 | 0.432 | 1.000 | 0.604 | 36.141 |

## Interpretation

- Strict ASR is 0.000 for every provenance defense because HIGH sinks without a
  structured grant never ALLOW; it cannot separate explicit lineage from
  reconstruction. The reviewer-sensitivity columns can.
- **Held-out test split:** explicit lineage alone BLOCKs 80.5% of attacks and
  leaves 19.5% to a human reviewer (missing or forged lineage → CONFIRM).
  Combined AgentTaint BLOCKs 100% with no benign false blocks.
- **Reconstruction split (broken USER-only lineage):** explicit lineage BLOCKs
  none of the 16 attacks. With the fixture embedder, reconstruction BLOCKs 13/16
  (all verbatim and re-formatted addresses; misses three hard cases where the
  uninstrumented step assembles or spells out the address) with 0/8 benign false
  blocks. With BAAI/bge-small-en-v1.5 on CPU it BLOCKs 16/16 but falsely BLOCKs
  3/8 benign controls (near-miss addresses and unrelated untrusted text). This is
  a real precision/recall trade-off, not a free improvement.
- Synthetic scenarios only; these numbers say nothing about production traffic.
