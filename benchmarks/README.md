# AgentTaint benchmarks

## Quick run

```bash
make install
make benchmark                 # fixture backend, held-out test
make benchmark-bge             # local BGE (requires reconstruction[semantic])
make benchmark-experiment      # multi-seed bootstrap (fixture)
python3 scripts/probe_agentdojo.py
```

## Layout

```
benchmarks/
  data/           # committed scenario JSON + VERSION (m7.1)
  reports/        # measured outputs (commit when claiming results)
```

## Rules

- Do not tune on `scenarios_test.json`.  
- Do not fabricate metrics.  
- Challenge probes are diagnostic only.  
- Fixture vs BGE must be reported as separate experiments.  
- AgentDojo probe ≠ AgentDojo ASR leaderboard.
