# AgentDojo subset — mercury-3 (inception)

Benchmark v1.2.1, attack `important_instructions_no_model_name`, seed 2120, 5 user tasks × 2 injection tasks per suite (banking,slack,workspace,travel). **Sampled subset, not the full suite.**

| defense | benign n | utility | attacked n | utility under attack | ASR (95% CI) | tool-action ASR (n) | blocked | confirm | errors |
|---|---|---|---|---|---|---|---|---|---|
| agenttaint-approve | 20 | 0.500 | 40 | 0.500 | 0.075 (0.03–0.20) | 0.000 (35) | 71 | 18 | 0 |
| agenttaint-strict | 20 | 0.350 | 40 | 0.325 | 0.050 (0.01–0.17) | 0.000 (35) | 39 | 53 | 0 |
| undefended | 20 | 0.850 | 40 | 0.700 | 0.075 (0.03–0.20) | 0.000 (35) | 0 | 0 | 0 |

Tool-action ASR excludes injection tasks whose goal needs no tool call (travel/injection_task_5, travel/injection_task_6); a tool-call firewall cannot stop those by design.
