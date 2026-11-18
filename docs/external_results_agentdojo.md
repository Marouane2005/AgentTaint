# AgentDojo with real LLMs: AgentTaint in front of the tools

**Status:** sampled subset of AgentDojo v1.2.1, free-tier models only. These are
the first numbers for AgentTaint on an external benchmark with a real model. They
are small samples with wide confidence intervals; read them as indicative.

## Setup

- **Benchmark:** AgentDojo 0.1.35, suites v1.2.1 (workspace, travel, banking,
  slack). Tasks, injections, attack and scoring are AgentDojo's, unmodified.
- **Attack:** `important_instructions_no_model_name` (the standard AgentDojo prompt
  injection, without naming the model).
- **Sample:** per suite, 5 user tasks and 2 injection tasks drawn with seed 2120;
  each user task is run once without injection (utility) and once per injection
  (utility under attack, ASR). 20 benign and 40 attacked runs per defense.
- **Pipeline:** AgentDojo system message → user query → model (OpenAI-compatible
  endpoint, rate-limited with backoff) → tool loop. AgentTaint replaces the tool
  executor (`AgentTaintToolsExecutor`): every tool call goes through the real
  `SecurityGateway` (risk tier → policy (Cedar) → audit), with tool results
  labelled as untrusted spans. The model never declares lineage, so authority
  arguments are checked by session-corpus reconstruction.
- **Trust registry:** `policies/agentdojo_trust_registry.yaml` (account facts
  TRUSTED/LOW, environment reads UNTRUSTED/LOW, calendar and file writes MEDIUM,
  sending, deleting, sharing, paying, booking and password changes HIGH).
- **Defenses:**
  - `undefended`: AgentDojo's own tool executor.
  - `agenttaint-strict`: CONFIRM is treated as declined (no human available).
  - `agenttaint-approve`: CONFIRM is approved through the real out-of-band
    confirmation service (simulates an always-approving human; upper bound on
    utility, lower bound on protection).
- **ASR** = AgentDojo's security check (the injection goal was achieved).
  **Tool-action ASR** excludes the two injection goals that are met by the text of
  the answer alone (`travel/injection_task_5`, `travel/injection_task_6`), which a
  tool-call firewall cannot stop by design.

Reproduce (keys from environment variables only; nothing is written to the repo):

```bash
pip install -e "./packages/benchmark[agentdojo]"
INCEPTION_API_KEY=... python scripts/run_agentdojo.py --provider inception \
  --model mercury-3 --suites banking,slack,workspace,travel \
  --user-tasks 5 --injection-tasks 2 --seed 2120 --min-interval 2 \
  --out benchmarks/reports/agentdojo/mercury-3
```

## Results: Inception `mercury-3` (free tier)

Full table: [benchmarks/external/agentdojo/mercury-3/summary.md](../benchmarks/external/agentdojo/mercury-3/summary.md).

| defense | utility (n=20) | utility under attack (n=40) | ASR (95% CI) | tool-action ASR (n=35) | tool calls BLOCKed | CONFIRMs |
|---|---|---|---|---|---|---|
| undefended | 0.850 | 0.700 | 0.075 (0.03–0.20) | 0.000 | 0 | 0 |
| agenttaint-strict | 0.350 | 0.325 | 0.050 (0.01–0.17) | 0.000 | 39 | 53 |
| agenttaint-approve | 0.500 | 0.500 | 0.075 (0.03–0.20) | 0.000 | 71 | 18 |

Per suite (utility / ASR):

| suite | undefended | strict | approve |
|---|---|---|---|
| banking | 1.00 / 0.00 | 0.40 / 0.00 | 0.60 / 0.00 |
| slack | 1.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| travel | 0.40 / 0.30 | 0.40 / 0.20 | 0.80 / 0.30 |
| workspace | 1.00 / 0.00 | 0.60 / 0.00 | 0.60 / 0.00 |

## What this shows, honestly

1. **This model already resists the tool-calling injections in the sample.**
   Undefended tool-action ASR is 0/35, so this run cannot show a security gain
   from AgentTaint on tool actions. Every successful attack, with or without
   AgentTaint, is `travel/injection_task_6` ("Say that I should absolutely visit
   Riverside View Hotel…"): the injected text ends up in the answer, with no tool
   call to stop. AgentTaint does not filter model output; that is out of scope
   and listed in the limitations.
2. **The utility cost is large.** Utility falls from 0.85 to 0.35 (strict) or
   0.50 (approve). In slack it falls to 0: user tasks there take recipients and
   channels from messages the agent reads (untrusted tool output), and
   `add_user_to_channel`, `send_channel_message` and `invite_user_to_slack` are
   BLOCKed by `block-inferred-untrusted-influence`. That is the policy working as
   designed (authority values derived from untrusted content), and it is the same
   utility/security trade-off reported for CaMeL-style information-flow control.
   Without a structured user grant for those values, AgentTaint cannot tell a
   legitimate data-dependent recipient from an injected one.
3. **Approving every CONFIRM does not reopen any tool attack** in this sample
   (tool-action ASR stays 0), but it only recovers part of the utility, because
   most lost tasks end in BLOCK, not CONFIRM.
4. A model that follows injections more readily is needed to measure protection
   on tool actions; a Gemini run is added separately when it completes.

## Limits of this evaluation

- Sampled subset (20 benign, 40 attacked runs per defense, 4 suites); confidence
  intervals are wide. Not comparable to full-suite leaderboard numbers.
- Free-tier models only; results depend on the model's own injection resistance.
- `agenttaint-approve` simulates a human who approves everything; real reviewers
  sit between strict and approve.
- One attack (`important_instructions_no_model_name`); adaptive attacks against
  AgentTaint's reconstruction were not run.
- Raw per-run logs (`runs.jsonl`) are not committed; only summaries.
