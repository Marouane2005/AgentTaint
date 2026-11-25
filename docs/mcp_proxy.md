# MCP Proxy — Milestone 2

## Role

The AgentTaint MCP proxy is the **enforcement boundary** between agents and tool backends. Every `tools/call` for configured backends must pass through `SecurityGateway` before execution.

## Supported MCP features (M2)

| Feature | Status |
|---------|--------|
| `tools/list` | Supported |
| `tools/call` | Supported (always enforced) |
| Result provenance labeling | Supported |
| Audit decisions | Supported |
| Structured BLOCK via `ToolError` | Supported |
| `agenttaint.preview` | Supported (no execution) |
| `agenttaint.audit_summary` | Supported |
| Resources / prompts | Not proxied yet |
| Multi-process stdio fan-out to remote MCP servers | Deferred (in-process composition for M2) |
| Cedar policies | Default engine (`engine: cedar`); see `docs/cedar_policy.md` |
| Confirmation binding | Supported via injected `ConfirmationService` (M5) |
| Reconstruction at invoke | Optional `ReconstructionEngine` + candidate corpus (M5) |

## Local mock email

`integrations/mock_email` provides fixture inbox/outbox tools:

- `email.read`
- `email.send`

No real network, accounts, or host mail.

## Policies

**Default (M9+):** `policies/provenance_policy.yaml` via `build_gateway_from_paths()`.

`policies/stub_policy.yaml` (M2 compatibility — load only when path name contains `stub`):

- `allow_by_default: true`
- `denylist_tools`
- `blocked_recipients` (e.g. `attacker@example.com`)

`policies/provenance_policy.yaml` (M5 / default):

- Provenance-aware BLOCK/CONFIRM/ALLOW with fail-closed HIGH-risk when registry unavailable
- See [security_integration.md](security_integration.md)

MCP compatibility boundary: [mcp_compatibility_m9.md](mcp_compatibility_m9.md).

## Run

```bash
make install
make test

# Optional stdio servers (for MCP clients)
python -m agenttaint_mock_email.server
python -m agenttaint_mcp_proxy.server
```

## Security properties (M2)

1. BLOCK/CONFIRM decisions never invoke the backend tool.
2. ALLOW decisions create a provenance span for the tool result (email bodies → `UNTRUSTED_TOOL`).
3. Audit records store argument **hashes** and **redacted** values, not raw secrets by default.
4. Risk classification is deterministic (trust registry), not LLM-based.

## Confirmation tokens, sessions and strict lineage

* **Approval token.** Approving a CONFIRM (`agenttaint approve approve <id>` or the
  dashboard) returns a single-use `approval_token` to the approver once. The agent
  retries the identical call with
  `_agenttaint: {"confirmation_id": ..., "approval_token": ...}`. A missing token is
  rejected; it is never read from the stored record. Tokens are not shown in list views.
* **Session binding.** Each proxy process has a session id (random, or
  `--session-id` / `AGENTTAINT_SESSION_ID`). Untrusted spans from other sessions or
  agents are not used for reconstruction. A different `session_id` or `agent_id`, or
  malformed `_agenttaint` metadata, yields `BLOCK` (`session-identity-mismatch`,
  `agent-identity-mismatch`, `malformed-agenttaint-metadata`).
* **Strict lineage.** In the proxy, declared parent spans must exist and belong to the
  calling agent; otherwise they resolve to UNKNOWN. Caller-supplied candidates are
  additive and never replace the session corpus. `agenttaint.*` tool names are reserved.
* **Read-only preview** never attaches provenance or consumes a confirmation.
* **Queue cap.** At most 50 pending confirmations per agent; further requests get
  `BLOCK` (`confirmation-queue-full`). Duplicate open requests are merged.
* **Known limit:** registry spans carry no session field, so cross-session filtering of
  stored spans is by agent only.
