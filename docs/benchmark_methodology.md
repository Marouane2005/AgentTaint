# Benchmark Methodology

**Status:** Plan (pre-implementation)  
**Rule:** Never invent results. Empty reports mean “not run.”

---

## Custom cross-agent transformation benchmark (primary for hypothesis)

### Scenario families

1. Direct malicious instruction in tool output  
2. Summarized malicious instruction  
3. Paraphrased instruction  
4. Extracted email/URL only  
5. Memory store → recall → sink  
6. Multi-agent delegation  
7. Multiple untrusted sources  
8. Conflicting USER vs UNTRUSTED  
9. Missing provenance metadata  
10. Benign similarity (FP probes)

### Protocol

- Generation scripts ≠ evaluation scripts.  
- Fixed RNG seeds.  
- Hold out test scenarios unused during threshold tuning.  
- Record defense config + ablation mode in each report JSON.

### Metrics

ASR, legitimate success, FPR, FNR, provenance P/R/F1 (where labels exist), decision accuracy, latency median/p95, graph size, CPU/RSS samples.

---

## AgentDojo / InjecAgent

Integrate when feasible. Follow official protocols. Document adapters and any excluded tasks. If integration is incomplete, say so—do not substitute custom numbers.

---

## Baselines

1. Undefended  
2. Prompt-injection classifier (open, local)  
3. Coarse taint (any untrusted read → block all HIGH)  
4. Explicit lineage only  
5. Reconstruction only  
6. Combined AgentTaint  

Label reimplementations clearly when original systems are not run.
