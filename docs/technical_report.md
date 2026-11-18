# AgentTaint: provenance-aware enforcement at the agent tool boundary

**Technical report · 18 November 2026 · Marouane El Aasri**

Every number in this report comes from an artifact in this repository; the
artifact is named next to the number. Claims the artifacts do not support are
listed as limitations, not made.

## Abstract

Tool-using AI agents read untrusted content (email, web pages, files, other
agents' messages) and then call tools that act on the world. Prompt injection
turns that content into instructions. AgentTaint is a policy enforcement point
placed at the tool boundary (an MCP proxy and a Python SDK). It keeps a
provenance graph of every span of content the agent handles, labels each span
with an origin and an epistemic status (`KNOWN`, `INFERRED`, `UNKNOWN`,
`PARTIAL`), reconstructs likely lineage when the agent does not declare it, and
decides each tool call (ALLOW, CONFIRM, BLOCK) with a Cedar policy over those
facts. CONFIRM is resolved only through an out-of-band, human-only approval
channel bound to the exact call.

On a held-out synthetic cross-agent suite (68 scenarios) AgentTaint stops every
attack with no benign false blocks; on a new broken-lineage split, reconstruction
blocks 13 of 16 attacks that explicit lineage alone sends to a reviewer. On a
sampled AgentDojo run with a real free-tier model (`mercury-3`), AgentTaint lets
no tool-action injection through, but the model resisted those injections
anyway, and utility fell from 0.85 to 0.35–0.50. The main lessons are that
information-flow enforcement at the tool boundary is cheap (median 6–7 ms per
decision) and robust to paraphrase and delegation within its threat model, and
that its utility cost on tasks whose legitimate arguments come from untrusted
data is the open problem, as it is for other IFC-style defenses.

## 1. Problem and threat model

Full threat model: [threat_model.md](threat_model.md). In short:

- **Assets:** the user's authority over side-effecting tools (send, pay, delete,
  share, write, execute) and the confidentiality of data reachable through tools.
- **Attacker:** controls content the agent reads (tool results, retrieved pages,
  documents, memory entries, other agents' messages). The attacker does not
  control the proxy, the policy, the confirmation secret or the approval channel.
- **Goal of the attacker:** make the agent call a high-risk tool with arguments
  (recipient, URL, IBAN, path, command) chosen by the attacker, possibly after
  summarization, paraphrase, memory round-trips or cross-agent delegation.
- **Out of scope:** manipulation of the final text answer without a tool call;
  a compromised model provider; side channels; attacks on the host OS.
- **Trust assumptions:** cooperating agents use the SDK or the proxy; the tool
  risk registry is correct; agents cannot reach the approval channel.

## 2. Design

### 2.1 Provenance graph with epistemic states

Every user instruction, tool result, summary, extraction, rewrite, memory write
and inter-agent message is a span with origin (`USER`, `TRUSTED_TOOL`,
`UNTRUSTED_TOOL`, `INTERNAL`, `UNKNOWN`) and status. Explicit edges
(`SUMMARIZED_FROM`, `TRANSFERRED_TO_AGENT`, `STORED_IN_MEMORY`, …) come from
instrumentation. Edges found by reconstruction are `INFERRED` and are never
promoted to `KNOWN`. Untracked transformations leave `GAP` markers so missing
lineage is visible rather than silently trusted. ([provenance_model.md](provenance_model.md))

### 2.2 Reconstruction

When a tool argument has no declared parents (an uninstrumented LLM call, a
broken pipeline), the gateway compares the argument with the session corpus of
untrusted spans using lexical, structural (normalized addresses, URLs, IBANs) and
semantic channels. Matches yield `INFERRED` evidence with scores; they are
scrutiny signals, not probabilities. Every channel can be ablated.
([reconstruction.md](reconstruction.md))

### 2.3 Policy

The gateway computes facts (risk tier, provenance status, untrusted influence,
inferred-only influence, declared lineage, structured user grants, recipient
lists, registry availability) and asks a Cedar policy set (20 policies, each
with an `@id`) for a decision. Two Cedar actions encode the three outcomes:
`execute` permitted → ALLOW, `execute_with_confirmation` permitted → CONFIRM,
neither → BLOCK (fail closed). A Python reference policy is kept and an
exhaustive parity test checks both engines agree on every fact combination.
([cedar_policy.md](cedar_policy.md))

### 2.4 Human-only confirmation

CONFIRM creates a record bound to tool, arguments hash, agent and provenance
context, with a TTL and single-use consumption (atomic APPROVED → CONSUMED,
durable in SQLite or Postgres). Approval is possible only through the CLI or the
dashboard approval screen, which requires a dedicated approver token distinct
from the dashboard read token. The MCP proxy exposes no approval tool.
([security_integration.md](security_integration.md), [dashboard.md](dashboard.md))

### 2.5 Enforcement point

`SecurityGateway` is the single chokepoint: risk tier → registry → confirmation
check → reconstruction evidence → policy → audit → backend. A non-ALLOW decision
never reaches the backend. The MCP proxy runs it in a separate process from the
agent; the shell backend runs commands in a Docker sandbox with no network,
read-only root, dropped capabilities and memory/CPU/pids limits (executed in CI).

## 3. Evaluation

### 3.1 Held-out synthetic suite and ablations

Source: [benchmark_results_m13.md](benchmark_results_m13.md) (68 scenarios: 41
attacks and 27 benign controls across 20 families; fixture embedder, seed 2120).

| defense | ASR | benign false BLOCK | utility | F1 (attribution) | median ms |
|---|---|---|---|---|---|
| undefended | 1.000 | 0.000 | 1.000 | n/a | 1.6 |
| coarse taint | 0.000 | 0.296 | 0.704 | n/a | 1.1 |
| explicit lineage only | 0.000 | 0.000 | 1.000 | n/a | 2.3 |
| reconstruction only | 0.000 | 0.000 | 1.000 | 0.988 | 5.5 |
| combined | 0.000 | 0.000 | 1.000 | 0.988 | 6.6 |

Channel ablation (reconstruction only): lexical and structural channels reach F1
0.988 each; the semantic channel alone reaches 0.211 with the fixture embedder.

### 3.2 Where reconstruction matters

Strict ASR cannot separate the provenance defenses because high-risk sinks never
ALLOW without a grant; the difference is whether an attack is blocked outright or
left to a human reviewer. Source: [benchmark_results_reconstruction.md](benchmark_results_reconstruction.md).

| split | defense | attacks BLOCKed | ASR if every CONFIRM approved | benign false BLOCK |
|---|---|---|---|---|
| test | explicit only | 0.805 | 0.195 | 0.000 |
| test | combined (fixture) | 1.000 | 0.000 | 0.000 |
| reconstruction | explicit only | 0.000 | 1.000 | 0.000 |
| reconstruction | combined (fixture) | 0.812 | 0.188 | 0.000 |
| reconstruction | combined (BGE-small, CPU) | 1.000 | 0.000 | 0.375 |

The `reconstruction` split has 16 attacks and 8 benign controls where an
uninstrumented step claims USER-only lineage. The fixture embedder misses three
attacks that assemble or spell out the address; BAAI/bge-small-en-v1.5 catches
them but falsely blocks 3 of 8 benign controls. That is a real precision/recall
trade-off.

### 3.3 Policy engine cost

Cedar and the Python reference produce identical decisions on the full suite.
Median/p95 decision latency, combined defense: 6.62/11.54 ms (Python) and
6.83/11.27 ms (Cedar). ([cedar_policy.md](cedar_policy.md))

### 3.4 Real LLM on AgentDojo (sampled subset)

Source: [external_results_agentdojo.md](external_results_agentdojo.md). AgentDojo
v1.2.1, unmodified tasks and `important_instructions` attack, 4 suites, 5 user ×
2 injection tasks per suite, `mercury-3` free tier.

| defense | utility | utility under attack | ASR | tool-action ASR |
|---|---|---|---|---|
| undefended | 0.850 | 0.700 | 0.075 | 0.000 |
| AgentTaint, CONFIRM declined | 0.350 | 0.325 | 0.050 | 0.000 |
| AgentTaint, CONFIRM approved | 0.500 | 0.500 | 0.075 | 0.000 |

All successful attacks are an answer-text goal (`travel/injection_task_6`) that
no tool firewall can stop. The model resisted every tool-action injection even
undefended, so this run measures cost, not protection. The cost is concentrated
in slack (utility 0), where recipients legitimately come from messages the agent
reads, and AgentTaint blocks authority values derived from untrusted content.

### 3.5 Security probes and systems tests

- Adversarial unit suite: forged metadata, races, replay, homoglyphs, missing
  lineage, self-approval, spoofed agent id (`tests/unit/test_m13_*`, `test_m15_*`).
- Postgres persistence and Docker sandbox limits execute in CI (`postgres`,
  `docker-sandbox` jobs; no skips allowed).
- End-to-end probes over the MCP proxy (no secret → refuse to start; untrusted
  `.bashrc` write → BLOCK; self-approval → unknown tool; replay → BLOCK).

## 4. Related work

**Prompt injection.** Greshake et al. showed indirect prompt injection against
LLM-integrated applications [1]. Benchmarks followed: **InjecAgent** [2] tests
single-step tool-call hijacking with simulated tools (direct harm and data
exfiltration cases); **AgentDojo** [3] provides stateful environments (workspace,
travel, banking, slack) with utility and security checks and pluggable defenses,
which is why AgentTaint's external evaluation uses it.

**Model-level and prompt-level defenses.** Delimiting or encoding untrusted data
(spotlighting [4]), training models to separate instructions from data (StruQ
[5]), and detectors/classifiers reduce injection success but give no guarantee
and do not track where a tool argument came from. AgentTaint does not include a
classifier baseline; that comparison is missing.

**System-level isolation.** The dual-LLM pattern [6] keeps a privileged model
away from untrusted text. **CaMeL** [7] makes this rigorous: a privileged LLM
writes a plan from the trusted query, a quarantined LLM parses untrusted data,
and an interpreter tracks capabilities on values and enforces policies at tool
calls. **FIDES** [8] attaches confidentiality and integrity labels to agent
context and enforces IFC policies in an agent framework, with selective hiding of
untrusted values. AgentTaint shares their premise (decide at the tool call from
provenance, not from the model's judgment) but differs in placement and
assumptions: it does not control the agent's planning loop, works as an MCP proxy
in front of unmodified agents, and accepts that lineage is often missing, so it
adds reconstruction with explicitly `INFERRED` status instead of requiring a
complete data-flow graph. The price is weaker guarantees: CaMeL's interpreter
sees every data dependency; AgentTaint sees only what is declared or
reconstructable. CapLite and NeuroTaint (see [related_work.md](related_work.md))
cover write-grounding and offline semantic taint respectively.

**Taint tracking.** Dynamic taint analysis marks data from untrusted sources and
propagates the mark through computation to check sinks: Perl's taint mode,
TaintCheck [9], TaintDroid [10]; Schwartz et al. survey the design space and its
over- and under-tainting pitfalls [11]. LLM transformations break the
propagation rules of classic taint tracking (a summary is a new string with no
byte-level dependency), which is the gap AgentTaint's reconstruction targets and
the reason its coarse-taint baseline over-blocks (0.296 benign false BLOCK).

**Information-flow control.** Denning's lattice model [12], noninterference
[13], Biba integrity [14], decentralized labels [15] and language-based IFC [16]
give the vocabulary AgentTaint uses (integrity of authority-bearing arguments,
declassification through explicit user grants). AgentTaint provides no
noninterference theorem: reconstruction is heuristic, and the policy is a
deny-by-default rule set over computed facts.

**Provenance and authorization.** Where/why-provenance [17] motivates span-level
lineage. Cedar [18] provides an analyzable policy language; AgentTaint uses it so
policies can be reviewed and tested apart from the gateway code. BGE embeddings
[19] provide the optional semantic channel.

## 5. Limitations

Complete list: [limitations.md](limitations.md). The ones that matter most:

1. Synthetic suites dominate the evidence; near-zero ASR there does not transfer
   to production agents.
2. The AgentDojo run is a small sample with one free-tier model that resisted the
   attacks; protection against tool-action injections on a susceptible model is
   not yet measured. InjecAgent was not run.
3. Utility loss when legitimate arguments derive from untrusted content (slack
   tasks) unless the user grants those values.
4. Reconstruction is heuristic: assembled or spelled-out values evade the fixture
   embedder; BGE trades that for benign false blocks.
5. Declared lineage is agent-asserted; a cooperating but buggy agent can declare
   wrong parents.
6. No output filtering: answer-text manipulation is out of scope.
7. No prompt-injection classifier baseline; no adaptive attacks targeting
   reconstruction thresholds.

## 6. Conclusion

A tool-boundary enforcement point with explicit epistemic provenance is cheap,
deployable in front of unmodified MCP agents and, within its threat model,
resilient to paraphrase, memory and delegation. Its value over explicit lineage
alone shows up exactly where instrumentation is broken. Its weakness is the
general weakness of information-flow defenses for agents: tasks whose correct
arguments come from untrusted data. Structured user grants and better
reconstruction precision are the next steps, followed by a larger external
evaluation on models that actually follow injections.

## References

1. K. Greshake et al. Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. AISec 2023. arXiv:2302.12173.
2. Q. Zhan, Z. Liang, Z. Ying, D. Kang. InjecAgent: Benchmarking indirect prompt injections in tool-integrated large language model agents. Findings of ACL 2024. arXiv:2403.02691.
3. E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, F. Tramèr. AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents. NeurIPS 2024 Datasets and Benchmarks. arXiv:2406.13352.
4. K. Hines et al. Defending against indirect prompt injection attacks with spotlighting. arXiv:2403.14720, 2024.
5. S. Chen, J. Piet, C. Sitawarin, D. Wagner. StruQ: Defending against prompt injection with structured queries. USENIX Security 2025. arXiv:2402.06363.
6. S. Willison. The dual LLM pattern (blog post, simonwillison.net), April 2023.
7. E. Debenedetti et al. Defeating prompt injections by design. arXiv:2503.18813, 2025.
8. M. Costa et al. Securing AI agents with information-flow control. arXiv:2505.23643, 2025.
9. J. Newsome, D. Song. Dynamic taint analysis for automatic detection, analysis, and signature generation of exploits on commodity software. NDSS 2005.
10. W. Enck et al. TaintDroid: An information-flow tracking system for realtime privacy monitoring on smartphones. OSDI 2010.
11. E. J. Schwartz, T. Avgerinos, D. Brumley. All you ever wanted to know about dynamic taint analysis and forward symbolic execution. IEEE S&P 2010.
12. D. E. Denning. A lattice model of secure information flow. CACM 19(5), 1976.
13. J. A. Goguen, J. Meseguer. Security policies and security models. IEEE S&P 1982.
14. K. J. Biba. Integrity considerations for secure computer systems. MITRE TR-3153, 1977.
15. A. C. Myers, B. Liskov. A decentralized model for information flow control. SOSP 1997.
16. A. Sabelfeld, A. C. Myers. Language-based information-flow security. IEEE JSAC 21(1), 2003.
17. P. Buneman, S. Khanna, W.-C. Tan. Why and where: A characterization of data provenance. ICDT 2001.
18. J. W. Cutler et al. Cedar: A new language for expressive, fast, safe, and analyzable authorization. OOPSLA 2024.
19. S. Xiao et al. C-Pack: Packaged resources to advance general Chinese embedding. arXiv:2309.07597, 2023.
