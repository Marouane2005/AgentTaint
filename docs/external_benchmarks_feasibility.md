# External benchmark feasibility — AgentDojo & InjecAgent (M9)

**Policy:** Do not force integration to claim support. Do not fabricate comparisons.

## AgentDojo

| Item | Assessment |
|------|------------|
| Official repo | [ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo) |
| Protocol | Dynamic suites; user tasks × injection tasks; metrics: benign utility, utility under attack, targeted ASR; environment-state checks (not LLM judges) |
| Runner | `python -m agentdojo.scripts.benchmark --model … --defense … --attack …` |
| Models | Designed around hosted LLM APIs (e.g. GPT-4o family in docs); model enum in package |
| Hardware | CPU feasible for orchestration; cost dominated by LLM calls |
| Free/local path | **No complete free path** for full ASR: requires paid/hosted (or self-hosted) LLM with AgentDojo model integration |
| Prior AgentTaint work | `benchmarks/reports/agentdojo_probe.json` — install + suite discovery only |
| Fair comparison | AgentDojo measures **prompt-injection agent pipelines**. AgentTaint measures **provenance-aware MCP tool enforcement**. Overlap exists only if AgentTaint is wired as a defense around AgentDojo tools **and** the same model/attack protocol is used |
| Unfair comparison | Quoting custom-suite ASR next to AgentDojo leaderboard numbers |
| M9 decision | **Not evaluated** for full ASR. Blocker: LLM-backed protocol + defense adapter engineering beyond free/local constraints |

### What a future adapter would need

1. Register AgentTaint as an AgentDojo defense wrapping tool calls.  
2. Map AgentDojo tool I/O into provenance spans + reconstruction candidates.  
3. Run official suites with a declared model and attack set.  
4. Publish raw AgentDojo logs alongside AgentTaint audit hashes.

Until then: mark **AgentDojo: not evaluated**.

## InjecAgent

| Item | Assessment |
|------|------------|
| Typical scope | Prompt-injection evaluation for tool-using agents (dataset/benchmark family; multiple public forks) |
| Free/local path | Generally requires LLM inference; not installed in this environment (`injecagent` import failed) |
| Fair comparison | Only with matching agent harness and attack definitions |
| M9 decision | **Not evaluated**. Blocker: dependency + LLM protocol not integrated; no fabricated scores |

## Summary

| Benchmark | Status |
|-----------|--------|
| Custom AgentTaint suite (M6/M7) | Evaluated (synthetic) |
| AgentDojo full ASR | **Not evaluated** |
| InjecAgent | **Not evaluated** |
