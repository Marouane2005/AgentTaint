# Cedar policy backend — deferred

## Status

Cedar (Amazon’s policy language) is **not** integrated. AgentTaint enforces
authorization through deterministic Python adapters (`StubPolicyAdapter`,
`ProvenanceAwarePolicy`) loaded from YAML.

## Why not cedarpy yet

1. **Pinned free/local stack:** the core engine must run without optional native
   extensions or network fetches. `cedarpy` / Cedar bindings add packaging and
   platform surface that is not required for the research claims.
2. **Evidence first:** the research contribution is provenance-aware *evidence*
   (KNOWN / INFERRED / UNKNOWN / PARTIAL) feeding fail-closed decisions. That
   can be validated without Cedar’s language runtime.
3. **Honesty:** claiming “Cedar-backed policy” without a tested cedarpy path
   would overstate the implementation.

## Adoption criteria (future)

- Add `cedarpy` (or equivalent) as an **optional** extra.
- Map `PolicyContext` fields into Cedar entities/attributes without silent
  provenance upgrades.
- Golden-file tests that prove identical ALLOW/BLOCK/CONFIRM outcomes for a
  fixture corpus under Python and Cedar backends.
- Document which Cedar features remain unused.

Until those land, policy documentation must say **Cedar deferred**, not Cedar
enforced.
