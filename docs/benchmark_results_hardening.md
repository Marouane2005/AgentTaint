# Hardening release (2026-11): fixes and before/after measurements

**Baseline:** `main` at `3f1b8cd` (before this release). **Current:** this release.
Both were installed with `make install` (Python 3.12, real `cedarpy` 4.12, SQLAlchemy 2.1,
`mcp` 1.30) and measured on the same CPU-only Linux machine on 2026-11-25, seed 2120.
Latencies are wall-clock on a shared machine and vary by about ±10% between runs.

## 1. Security fixes in this release

1. **Semantic-only promotion:** semantic similarity alone can no longer promote an email,
   URL, path or shell command to INFERRED; weak structural/domain overlap or session
   context is required. Lists and nested values are reconstructed leaf by leaf.
2. **Declared lineage bypass:** declared lineage or caller-supplied candidates could switch
   off session-wide reconstruction. Reconstruction now always runs for MEDIUM and HIGH
   calls and declared lineage is extra evidence only. A reconstruction miss on a declared
   argument does not downgrade it, and an undeclared argument still fails closed.
3. **Forged or foreign parent spans:** declared parents are checked against the registry
   and the calling agent; the reconstruction corpus is isolated per agent and session.
4. **Session spoofing:** `session_id` is bound to the connection; caller-supplied values
   are rejected.
5. **Malformed `_agenttaint` metadata** is rejected instead of silently dropped.
6. **Tool-name shadowing:** a backend cannot register `agenttaint.*` tools;
   `agenttaint.preview` is read-only.
7. **Approval token:** executing an approved call requires the single-use
   `approval_token` given to the approver (the gateway no longer reads it from the stored
   record). Concurrent replays execute at most once.
8. **Confirmation flooding:** atomic de-duplication of retried calls and a per-agent cap on
   pending confirmations; an approval is released if the request is cancelled before the
   backend call.
9. **Event-loop stalls:** policy evaluation, labelling and audit run on worker threads.
10. **Audit gap on crash:** ALLOW decisions are written ahead of the backend call and
    updated with the outcome (`AuditStore.update`).
11. **Grant gaps:** more authority arguments (`cc`, `bcc`, `cwd`, `args`, `uri`, `target`,
    `recipients`, `endpoint`), one grant per list element, case-sensitive paths and
    commands.
12. **Cedar policy ids:** all 20 rules have unique ids; the parity test checks uniqueness
    and that the Python reference only emits ids defined in Cedar.
13. **Benchmark fidelity:** the runner no longer monkey-patches a private gateway method;
    the ablation is an explicit `reconstruction_ablation` field.
14. **Spelled-out addresses** ("alice at evil dot com") are matched at MODERATE support only
    when the local part and the spelled domain appear in order.

**Behaviour change:** clients must now pass both `confirmation_id` and `approval_token`
in `_agenttaint` when retrying an approved call. A confirmation id alone is rejected.

## 2. Benchmark: baseline vs current

`python -m agenttaint_benchmark run --split <split> --seed 2120 --semantic-backend fixture`,
combined defense. Current reports:
[`report_test_fixture_480f0c5f.md`](../benchmarks/reports/report_test_fixture_480f0c5f.md),
[`report_test_bge_30821f52.md`](../benchmarks/reports/report_test_bge_30821f52.md).

| split | n | metric | baseline | current |
|---|---|---|---|---|
| test (held-out) | 68 | ASR / benign BLOCK / benign CONFIRM | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| test | 68 | precision / recall / F1 | 1.000 / 0.976 / 0.988 | 1.000 / 0.976 / 0.988 |
| dev | 7 | ASR / FPR_block / P / R / F1 | 0.000 / 0.000 / 1.000 / 0.875 / 0.933 | identical |
| challenge | 4 | ASR / P / R / F1 | 0.000 / 1.000 / 0.667 / 0.800 | identical |
| reconstruction | 24 | ASR / benign BLOCK / benign CONFIRM | 0.000 / 0.000 / 0.750 | 0.000 / 0.000 / 0.750 |
| reconstruction | 24 | precision / recall / F1 | 0.448 / 0.812 / 0.578 | 0.467 / 0.875 / 0.609 |
| test, median / p95 latency | 68 | ms (4 baseline runs, 6 current runs) | 7.1–7.4 / 11.7–12.6 | 8.4–9.1 / 13.3–14.4 |

With local BGE embeddings (`--semantic-backend bge`, BAAI/bge-small-en-v1.5 on CPU):

| split | metric | baseline | current |
|---|---|---|---|
| test (68) | ASR / benign BLOCK / benign CONFIRM | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| test (68) | precision / recall / F1 | 0.988 / 1.000 / 0.994 | 1.000 / 1.000 / 1.000 |
| reconstruction (24) | attack BLOCK / benign BLOCK | 1.000 / 0.375 | 1.000 / 0.000 |
| reconstruction (24) | precision / recall / F1 | 0.432 / 1.000 / 0.604 | 0.500 / 1.000 / 0.667 |
| test, median / p95 latency (warm model, 2 runs each) | ms | 38–46 / 90–131 | 73–76 / 181–183 |

Reading: no attack is ALLOWed on any split before or after. The only decision changes are
improvements: one more reconstruction-split attack is detected with the fixture embedder
(spelled-out address), and with BGE the three benign false blocks on the reconstruction
split are gone because semantic similarity alone no longer promotes structured arguments.
The trade-off is latency: always-on session reconstruction costs about 1.5 ms per decision
with the fixture embedder and roughly doubles decision time with BGE.

## 3. Declared lineage no longer bypasses reconstruction

`python scripts/run_declared_lineage_eval.py --split <split>` runs the combined defense
with three corpus sources: `candidates` (the harness hands over the corpus), `session`
(only what the gateway labelled itself, as the MCP proxy runs) and `none` (emulates a
gateway that skips reconstruction once lineage is declared, the behaviour before this
release).

| split | arm | attacks: n, ALLOW / BLOCK / CONFIRM | benign: n, ALLOW / BLOCK / CONFIRM |
|---|---|---|---|
| test | candidates, session | 41: 0 / 41 / 0 | 27: 27 / 0 / 0 |
| test | none (before) | 41: 0 / 33 / 8 | 27: 27 / 0 / 0 |
| challenge | candidates, session | 4: 0 / 3 / 1 | n/a |
| challenge | none (before) | 4: 0 / 2 / 2 | n/a |
| reconstruction | candidates, session | 16: 0 / 14 / 2 | 8: 2 / 0 / 6 |
| reconstruction | none (before) | 16: 0 / 0 / 16 | 8: 2 / 0 / 6 |
| dev | all arms | 5: 0 / 5 / 0 | 2: 2 / 0 / 0 |

Without session reconstruction, 8 test-split attacks (forged-lineage, lineage-gap and
cross-agent-no-lineage families) fall from BLOCK to CONFIRM, where a human could approve
them. With it they are blocked. Benign decisions are identical in every arm, so the change
added no false positives on these splits.

## 4. Test suites run for this release

| suite | result |
|---|---|
| `PYTHONHASHSEED=0 pytest` (full, real cedarpy/SQLAlchemy/mcp) | 384 passed, 18 skipped (baseline: 269 passed, 18 skipped) |
| `pytest -m postgres` against PostgreSQL 17 | 6 passed, 1 skipped (AgentDojo extra not installed) |
| `ruff check`, `ruff format --check` | clean |
| `make typecheck` (mypy) | no issues in 56 source files |
| dashboard `npm test` / `npm run lint` / `tsc --noEmit` / `npm run build` | 22/22 passed, clean, clean, built |

The 18 local skips are the Docker shell-sandbox tests (no Docker on the measuring
machine), the Postgres tests in the default run (they run in the `-m postgres` pass
above) and the optional AgentDojo adapter test. CI runs all three with skips disallowed.
