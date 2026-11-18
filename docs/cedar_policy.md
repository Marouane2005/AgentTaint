# Cedar policy engine

**Status:** enforced by default since the `cedar-policy-engine` change. The MCP
proxy (`build_gateway_from_paths`), the control-plane demo gateway and the
benchmark's provenance defenses all decide through Cedar via
[`cedarpy`](https://pypi.org/project/cedarpy/) (local Rust engine; no network,
no paid service).

## Files

| File | Purpose |
|------|---------|
| `packages/policy/src/agenttaint_policy/cedar/agenttaint.cedar` | The 20 authorization policies, each with an `@id` equal to the audited `policy_id` |
| `packages/policy/src/agenttaint_policy/cedar/agenttaint.cedarschema.json` | Cedar schema: `Agent`, `Tool`, actions `execute` and `execute_with_confirmation`, typed request context |
| `packages/policy/src/agenttaint_policy/cedar_engine.py` | `CedarProvenancePolicy` (PolicyAdapter) |
| `policies/provenance_policy.yaml` | `engine: cedar` (default) or `engine: python` (reference) plus the config flags |

## How a decision is made

1. The gateway computes deterministic **facts** for the call (all required,
   schema-typed): risk tier, provenance status, registry availability,
   denylist membership, bound-confirmation validity, structured-grant coverage
   of every authority argument, blocked recipient, untrusted influence,
   inferred-only influence, declared lineage, session-has-seen-untrusted, and
   the five policy configuration flags (`cfg_*`).
2. Cedar evaluates `Action::"execute"`:
   - permitted → **ALLOW**
   - denied by a named `forbid` → **BLOCK**
3. Otherwise Cedar evaluates `Action::"execute_with_confirmation"`:
   - permitted → **CONFIRM** (human, out-of-band approval)
4. Anything else → **BLOCK** `cedar-default-deny` (fail closed).

If several policies match, the first in file order is recorded as the
`policy_id`, mirroring the ordered rules of the Python reference. Requests are
validated against the schema: a missing or mistyped fact is an evaluation error
and becomes **BLOCK** `cedar-evaluation-error`. Invalid policies, a policy
without `@id`, or a missing `cedarpy` raise `CedarPolicyError` at load time; there
is no silent fallback to another engine.

## Parity with the Python reference

`tests/unit/test_cedar_policy_parity.py` compares `CedarProvenancePolicy` and
`ProvenanceAwarePolicy` on every combination of:

- 3 tool/argument shapes (allowed recipient, blocked recipient, denylisted tool)
- 3 risk tiers × 4 provenance statuses
- grant / no grant, and 6 boolean facts (registry, confirmation, untrusted,
  inferred-only, lineage declared, session saw untrusted)
- all 32 combinations of the 5 configuration flags

That is 147,456 comparisons of `(decision, policy_id)`; all match. The
benchmark test split gives identical metrics under both engines (see below).

| Defense (68 scenarios, seed 2120) | ASR | utility | median / p95 ms (python) | median / p95 ms (cedar) |
|---|---|---|---|---|
| explicit_only | 0.000 | 1.000 | 2.47 / 4.20 | 3.17 / 5.17 |
| combined | 0.000 | 1.000 | 6.62 / 11.54 | 6.83 / 11.27 |

Cedar adds roughly 0.2–0.7 ms per decision on this machine (two authorization
calls for CONFIRM paths).

## What Cedar does and does not do here

- Cedar owns the **decision logic** (rule ordering, fail-closed handling,
  configuration flags). Provenance facts are still computed in Python by the
  gateway and the reconstruction engine; Cedar cannot see raw content.
- Entities are minimal (`Agent`, `Tool`); per-tool or per-agent attributes,
  templates and entity hierarchies are not used yet.
- The legacy `StubPolicyAdapter` (M2) is unchanged and not Cedar-backed.
