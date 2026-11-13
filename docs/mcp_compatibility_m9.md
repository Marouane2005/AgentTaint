# MCP compatibility assessment (M9)

## Honest boundary

AgentTaint’s MCP path is a **FastMCP server** that exposes selected tools and runs each `tools/call` through `SecurityGateway` **in-process**.

It is **not** claimed as a drop-in multi-process MCP proxy conforming to every protocol feature against arbitrary third-party servers.

## Feature matrix (tested vs claimed)

| Feature | Status | Evidence |
|---------|--------|----------|
| `tools/list` | Supported / tested | `tests/integration/test_mcp_proxy_email.py` via `create_connected_server_and_client_session` |
| `tools/call` enforcement | Supported / tested | Same; BLOCK paths assert backend sink empty |
| Result labeling + `_agenttaint` meta | Supported / tested | Read path |
| `agenttaint.preview` | Supported / tested | Listed in tools |
| `agenttaint.audit_summary` | Supported | Server registration |
| Structured deny via `ToolError` | Supported / tested | Blocked send |
| Resources | **Not proxied** | Documented |
| Prompts | **Not proxied** | Documented |
| Sampling / roots / elicitation | **Not claimed** | — |
| Stdio multi-process client ↔ proxy ↔ remote MCP server | **Not fully tested** | Deferred; in-memory session used in CI |
| Confirmation / parent spans / candidates on tool schema | **Not on MCP wire** | Available on `SecurityGateway.invoke` only |
| Default policy | Provenance-aware (M9 fix) | `build_gateway_from_paths` |

## Integration test architecture

Current reproducible test:

```
MCP client session  ↔  (in-memory transport)  ↔  FastMCP AgentTaint proxy
                                              └─ SecurityGateway → MockEmailBackend
```

This validates enforcement wiring and tool discovery. It does **not** prove wire compatibility with every MCP SDK version or remote transport.

## M9 stance

Call the system:

> “MCP tool-call enforcement proxy (FastMCP), with tested list/call/deny paths for mock email.”

Do **not** call it:

> “Fully MCP-compatible for all clients/servers.”
