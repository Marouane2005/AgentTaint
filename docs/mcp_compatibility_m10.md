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
| `_agenttaint.confirmation_id` / `approval_token` | Supported / tested | Wire helpers + approve tool |
| `_agenttaint.argument_parent_span_ids` | Supported / tested | Gateway invoke path |
| `_agenttaint.candidates` | Supported | Reconstruction corpus on wire |
| `agenttaint.approve_confirmation` | Supported / tested | Protocol proxy tool |
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
  "approval_token": "...",
  "argument_parent_span_ids": {"to": ["span-id"]},
  "candidates": [{"span_id": "...", "text": "...", "origin": "UNTRUSTED_TOOL"}],
  "agent_id": "agent_a",
  "session_id": "sess-1",
  "provenance_context_hash": "optional-override"
}
```

## Mock downstream servers

| Server | Tools | Notes |
|--------|-------|-------|
| `agenttaint_mock_email` | `email.read`, `email.send` | Fixtures only |
| `agenttaint_mock_filesystem` | `filesystem.read`, `filesystem.write` | Temp sandbox root |
| `agenttaint_mock_http` | `http.get`, `http.post` | No real network |
| `agenttaint_mock_shell` | `shell.execute` | Docker required; refuses host shell |

## Do not claim

> “Fully MCP-compatible for all clients/servers.”

Do claim:

> “Stdio MCP tool-call enforcement proxy with tested list/call/deny paths and
> multi-process client↔proxy↔backend wiring for mock email/filesystem/http/shell.”
