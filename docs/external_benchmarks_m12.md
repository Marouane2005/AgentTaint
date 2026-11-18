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

This addresses the review finding that `explicit_only` matched `combined` on
every metric because parents were always wired.

## Fair comparison note

AgentDojo measures prompt-injection agent pipelines. AgentTaint measures
provenance-aware MCP tool enforcement. Numbers are comparable only under a
shared harness that preserves both protocols. Until that exists, label external
benchmarks **not evaluated**.
