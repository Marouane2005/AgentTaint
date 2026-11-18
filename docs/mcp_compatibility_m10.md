# MCP compatibility assessment (M10)

## Honest boundary

AgentTaint provides:

1. **Protocol proxy** (`agenttaint_mcp_proxy.protocol_proxy`): a real MCP *server* to
   upstream clients and a real MCP *client* to a downstream tool server over **stdio**.
2. **Legacy FastMCP helper** (`create_security_proxy`): in-process composition for unit
   demos. Prefer the protocol proxy for multi-process claims.

This is **not** a claim of full MCP specification conformance across every transport,
SDK version, or optional capability.

## Feature matrix

| Feature | Status | Evidence |
|---------|--------|----------|
| `tools/list` | Supported / tested | Multi-process + in-process tests |
| `tools/call` enforcement | Supported / tested | BLOCK/CONFIRM before backend forward |
| Real backend `inputSchema` forwarded | Supported / tested (protocol proxy) | Augmented with `_agenttaint` |
| `_agenttaint.confirmation_id` | Supported / tested | Retry after out-of-band approval (M15) |
| `_agenttaint.argument_parent_span_ids` | Supported / tested | Gateway invoke path |
| `_agenttaint.candidates` | Supported | Reconstruction corpus on wire |
| Approval over MCP | **Removed (M15)** | The agent-facing surface has no approval tool; approvals come only from the CLI or the token-gated control plane |
| Caller-supplied `agent_id` | **Rejected (M15)** | Identity comes from `--agent-id` proxy configuration |
| `agenttaint.preview` | Supported / tested | Protocol + FastMCP |
| Result `_agenttaint` meta | Supported / tested | Span/decision metadata |
| Resources | **Not proxied** | — |
| Prompts | **Not proxied** | — |
| Sampling / roots / elicitation | **Not claimed** | — |
| Cancellation | Partial | Pre-forward cancel check; mid-flight backend may complete |
| Streamable HTTP / SSE transports | **Untested** | Stdio only in CI |
| Multi-process stdio client↔proxy↔server | Supported / tested | `test_m10_multiprocess_proxy.py` |

## `_agenttaint` metadata object

```json
{
  "confirmation_id": "...",
  "argument_parent_span_ids": {"to": ["span-id"]},
  "candidates": [{"span_id": "...", "text": "...", "origin": "UNTRUSTED_TOOL"}],
  "session_id": "sess-1"
}
```

Changes in M15:

- `agent_id` is **not** accepted from the caller. The proxy uses the identity it
  was started with (`--agent-id`); a different caller-supplied value is rejected
  (and the published input schema does not allow the field).
- `provenance_context_hash` is always computed server-side from the declared
  parents and candidates; a caller-supplied value is ignored.
- `approval_token` is no longer part of the published schema. Tokens stay in the
  security database; after a human approves out-of-band the agent retries the
  exact call with only `confirmation_id`.

## Confirmation flow (M15)

1. The agent calls a tool; policy returns CONFIRM with a `confirmation_id`.
2. A human reviews and approves **outside the agent's reach**:
   - CLI: `python3 -m agenttaint_agent_sdk.confirm_cli list|show|approve|deny`
   - Control plane: `GET /api/v1/confirmations`, `POST /api/v1/confirmations/{id}/approve|deny`
     (always requires `X-AgentTaint-Token`; disabled when no token is configured).
3. The agent retries the identical call with `_agenttaint.confirmation_id`. The
   approval is single-use and bound to tool, argument hash, agent identity and
   provenance context.

The proxy refuses to start unless `AGENTTAINT_CONFIRM_SECRET` is set to a random
value of at least 32 characters (no built-in default):

```bash
export AGENTTAINT_CONFIRM_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Proxy secrets (`AGENTTAINT_CONFIRM_SECRET`, dashboard token, database URLs,
envelope keys) are stripped from the environment passed to downstream servers.

## Mock downstream servers

| Server | Tools | Notes |
|--------|-------|-------|
| `agenttaint_mock_email` | `email.read`, `email.send` | Fixtures only |
| `agenttaint_mock_filesystem` | `filesystem.read`, `filesystem.write` | Temp sandbox root |
| `agenttaint_mock_http` | `http.get`, `http.post` | No real network |
| `agenttaint_mock_shell` | `shell.execute` | Docker required; refuses host shell. Container limits: no network, read-only rootfs, `--cap-drop ALL`, `--user 65534:65534`, 256 MiB memory, 0.5 CPU, 64 pids, 10 s kill timeout (command line unit-tested; container behaviour checked in the CI `docker-sandbox` job) |

## Do not claim

> “Fully MCP-compatible for all clients/servers.”

Do claim:

> “Stdio MCP tool-call enforcement proxy with tested list/call/deny paths and
> multi-process client↔proxy↔backend wiring for mock email/filesystem/http/shell.”
