# AgentTaint benchmarks

## Quick run

```bash
make install
make benchmark
```

Writes JSON + Markdown under `benchmarks/reports/` and updates `latest_test.*` symlinks.

## Layout

```
benchmarks/
  data/           # committed scenario JSON + VERSION
  reports/        # measured outputs (commit when claiming results)
```

## Rules

- Do not tune on `scenarios_test.json`.  
- Do not fabricate metrics.  
- Challenge probes are diagnostic only.
