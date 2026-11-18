# External benchmarks — M12 reassessment

**Policy:** Do not weaken AgentDojo/InjecAgent protocols. Do not fabricate scores.

## Free/local feasibility (re-checked)

| Benchmark | Importable here | Free/local full ASR | Decision |
|-----------|-----------------|---------------------|----------|
| AgentDojo | No (`agentdojo` not installed) | No — requires LLM model integration | **Not evaluated** |
| InjecAgent | No | No — requires LLM agent harness | **Not evaluated** |

Adapter stubs live in `agenttaint_benchmark.external_adapters` and raise
`ExternalBenchmarkNotEvaluated` rather than returning placeholder metrics.

## Custom suite expansion (evaluated)

Dataset `2026.11.18-m12.1`:

- `missing_lineage` scenarios now use `argument_parent_mode=none` so
  **explicit_only** cannot rely on parent spans.
- Added cross-agent no-lineage attacks where reconstruction must carry detection.

**Correction (M15):** this was intended to separate `explicit_only` from
`combined`, but on the measured test split (68 scenarios, seed 2120, fixture
embedder) the two still match on every decision metric:

| config | ASR | FNR | FPR_block | FPR_confirm | utility |
|--------|-----|-----|-----------|-------------|---------|
| explicit_only | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| combined | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| coarse_taint | 0.000 | 0.000 | 0.296 | 0.000 | 0.704 |
| undefended | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |

The no-lineage scenarios are stopped by fail-closed handling of UNKNOWN
provenance (CONFIRM/BLOCK), not by reconstruction. Reconstruction contributes
inspectable evidence (provenance P=1.000, R=0.976, F1=0.988 for `combined`), but
**its added decision value over explicit lineage is not demonstrated on the
current suite.** A suite where reconstruction changes outcomes (for example,
scenarios where UNKNOWN is allowed by policy and only reconstruction can flag
influence) is still needed.

## Fair comparison note

AgentDojo measures prompt-injection agent pipelines. AgentTaint measures
provenance-aware MCP tool enforcement. Numbers are comparable only under a
shared harness that preserves both protocols. Until that exists, label external
benchmarks **not evaluated**.
