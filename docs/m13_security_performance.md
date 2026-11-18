# Milestone 13 — Security & performance evaluation

## Goals

Reproducible adversarial coverage plus measured latency/memory and channel
ablations on the held-out custom suite. Raw JSON reports stay under
`benchmarks/reports/` (gitignored); markdown summaries are committed.

## Adversarial coverage

| Threat class | Where exercised |
|--------------|-----------------|
| Provenance forgery (sender rewrite) | `test_m13_adversarial_evaluation.py`, M11 keyring tests |
| Cross-agent envelope transfer | M13 accept/lineage test; M10 multiprocess proxy |
| Confirmation bypass (arg mutation) | M13 + M9 confirmation tests |
| Confirmation races | Durable SQLite atomic consume (10 threads → 1 winner) |
| Normalization / homoglyph grants | Cyrillic lookalike vs ASCII grant |
| Missing lineage | HIGH sink without parents → CONFIRM/BLOCK |
| Conflicting evidence | Untrusted parent + wrong grant → deny |
| False positives (authorized benign) | Grant + USER parent → ALLOW |
| Resource exhaustion (large corpus) | 200 candidates, soft latency bound |
| Replay | Envelope nonce store |
| Latency overhead | Gateway preview microbench |

## Ablations

Under `reconstruction_only`:

- lexical
- structural
- semantic
- lexical_structural
- explicit
- combined (primary matrix)

Primary defenses: undefended, coarse_taint, explicit_only, reconstruction_only,
combined.

## How to reproduce

```bash
PYTHONHASHSEED=0 python scripts/run_m13_evaluation.py \
  --split test --seed 2120 --semantic-backend fixture --tag m13
PYTHONHASHSEED=0 pytest -q
```

Optional variability (bootstrap, not stochastic model noise):

```bash
PYTHONHASHSEED=0 python -m agenttaint_benchmark experiment \
  --split test --semantic-backend fixture --tag m13_experiment
```

## Honesty notes

- Zero ASR on the synthetic suite is **not** general attack prevention.
- Fixture embeddings are not calibrated production embeddings.
- AgentDojo / InjecAgent remain **not evaluated** without an LLM.
- Prior M7/M12 markdown result docs are preserved; M13 is additive.
