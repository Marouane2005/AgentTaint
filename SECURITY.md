# Security policy

AgentTaint is a security control, so vulnerability reports are very welcome.

## Supported versions

| Version | Supported |
|---|---|
| `main` and the latest 1.x release | Yes |
| Older releases | No; please upgrade first |

## Reporting a vulnerability

Please **do not open a public issue** for a vulnerability.

Report it privately through GitHub:
[Report a vulnerability](https://github.com/Marouane2005/agenttaint/security/advisories/new)
(the repository's **Security** tab, then **Report a vulnerability**).

Include as much of the following as you can:

- the affected component (proxy, gateway, policy, reconstruction, confirmations, API,
  dashboard, CLI) and version or commit;
- a description of the issue and its impact, for example a tool call that should have
  been blocked or held for confirmation but was allowed;
- steps or a minimal script to reproduce it, ideally against the mock backends in
  `integrations/`;
- any suggested fix.

## What to expect

- An acknowledgement within 7 days.
- An assessment and, for a confirmed issue, a planned fix within 30 days. Complex issues
  may take longer; you will be kept informed.
- Credit in the release notes and the advisory, unless you prefer to stay anonymous.

Please give a reasonable time to release a fix before disclosing publicly.

## Scope

In scope: ways to make AgentTaint allow a high- or medium-risk tool call that its policy
should block or hold, to forge or bypass provenance or confirmations, to read or change
the audit log or approvals without the right token, and fail-open behaviour on errors.

Out of scope: issues in third-party MCP servers or models, attacks that need control of
the machine running the proxy, and the known limitations in
[docs/limitations.md](docs/limitations.md) (for example, results on the synthetic
benchmark are not a guarantee against real attacks).
