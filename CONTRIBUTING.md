# Contributing to AgentTaint

## Principles

1. Prefer correctness and tests over feature volume.
2. Never invent benchmark numbers or citations.
3. Do not upgrade INFERRED provenance to KNOWN.
4. Keep the core engine free of mandatory paid APIs.
5. Record failed approaches in `research_log/`.

## Development

```bash
make install
make test
make lint
```

Follow milestones in `docs/implementation_plan.md`.

## Pull requests

- Include tests for security-sensitive changes.
- Update `docs/limitations.md` when guarantees change.
- Do not claim Cedar / AgentDojo / dashboard capabilities that are not implemented.
