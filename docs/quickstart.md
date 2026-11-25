# Quickstart: put AgentTaint in front of any MCP server

AgentTaint runs as a **stdio MCP proxy**. Your MCP client launches
`agenttaint proxy` instead of the server; the proxy launches the real server as a
child process and forwards only the tool calls its policy allows. Calls it does
not allow are answered with `BLOCK`, or held as `CONFIRM` until a person approves
them out of band (`agenttaint approve` or the dashboard's Confirmations page).

Time needed: about 10 minutes. Requirements: Python 3.12+, and Node.js if the
MCP server you protect is an `npx` package.

## 1. Install

AgentTaint is open source (Apache-2.0). Install from a source checkout:

```bash
git clone https://github.com/Marouane2005/AgentTaint.git && cd AgentTaint
python3 -m venv ~/.agenttaint-venv
source ~/.agenttaint-venv/bin/activate
make install                       # editable install of every package in this checkout
agenttaint --version
```

If your checkout was built with `scripts/build_release.sh`, install from the
bundled wheels instead: `pip install --no-index --find-links wheels agenttaint`
(the wheels target Linux x86_64 / CPython 3.12; drop `--no-index` elsewhere).

GUI clients (Claude Desktop, Cursor) do not inherit your virtualenv's `PATH`.
`agenttaint connect` therefore prints the absolute path of the installed script.

## 2. Create a configuration

```bash
agenttaint init ~/agenttaint --backend "npx -y @modelcontextprotocol/server-filesystem $HOME/projects"
agenttaint doctor --config ~/agenttaint/agenttaint.yaml   # checks config, secrets, backend
```

Without `--backend`, `init` points at a sandbox folder under the target
directory so the first run works. Use `--client claude-desktop|cursor|claude-code`
to print the client snippet at the same time.

This writes:

| File | Purpose |
|------|---------|
| `agenttaint.yaml` | proxy, storage and dashboard settings ([reference](configuration.md)) |
| `policies/provenance_policy.yaml` | the Cedar-backed flow policy |
| `policies/trust_registry.yaml` | risk tier and result trust per tool |
| `.env` (mode 600) | generated secrets and local SQLite URLs; values are never printed |

## 3. Point it at your MCP server

Edit `backend.command` in `agenttaint.yaml`. Examples:

```yaml
backend:
  command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/home/you/projects"]
```

```yaml
backend:
  command: ["uvx", "mcp-server-fetch"]
```

Then list that server's tools in `policies/trust_registry.yaml`. The tool names
are what the server reports in `tools/list`:

```yaml
tools:
  read_file:
    integration_trust: TRUSTED_TOOL_SERVER
    result_origin: UNTRUSTED_TOOL   # file contents are data, not instructions
    default_risk: LOW
  write_file:
    integration_trust: TRUSTED_TOOL_SERVER
    result_origin: INTERNAL
    default_risk: MEDIUM
  fetch:
    integration_trust: TRUSTED_TOOL_SERVER
    result_origin: UNTRUSTED_TOOL
    default_risk: HIGH              # sends data to the network
```

Tools you do not list get `defaults.default_risk` (MEDIUM). Mark anything that
sends data out (email, HTTP POST, messaging, payments, shell) as `HIGH`: those are
the calls the policy checks against provenance.

Try it without a real server first: `agenttaint proxy --demo-backend` protects
a built-in mock email server.

## 4. Configure your MCP client

`agenttaint connect <client> --config ~/agenttaint/agenttaint.yaml` prints a snippet
like the ones below with absolute paths filled in (it names the server
`agenttaint-protected`; rename it freely). Remove the server's original entry so the
client cannot call it directly.

### Claude Desktop

Settings → Developer → Edit Config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "files-protected": {
      "command": "/home/you/.agenttaint-venv/bin/agenttaint",
      "args": ["proxy", "--config", "/home/you/agenttaint/agenttaint.yaml"]
    }
  }
}
```

### Cursor

`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project):

```json
{
  "mcpServers": {
    "files-protected": {
      "command": "/home/you/.agenttaint-venv/bin/agenttaint",
      "args": ["proxy", "--config", "/home/you/agenttaint/agenttaint.yaml"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add files-protected -- \
  /home/you/.agenttaint-venv/bin/agenttaint proxy --config /home/you/agenttaint/agenttaint.yaml
```

### Proxy inside Docker

With the compose stack from [operations.md](operations.md) running:

```json
{
  "mcpServers": {
    "files-protected": {
      "command": "docker",
      "args": ["compose", "-f", "/home/you/agenttaint/docker-compose.yml",
               "run", "--rm", "-i", "-T", "proxy"]
    }
  }
}
```

The backend server then runs inside the AgentTaint container, so paths in
`backend.command` must exist there (mount them in `docker-compose.yml`).

Restart the client, make a tool call, then check what the gateway decided:

```bash
agenttaint log --config ~/agenttaint/agenttaint.yaml      # ALLOW / CONFIRM / BLOCK, color-coded
```

## 5. Approve a held call (CONFIRM)

A `CONFIRM` decision is never self-service for the agent. A person approves it
out of band, and the single-use approval token is shown to the approver once:

```bash
agenttaint approve list    --config ~/agenttaint/agenttaint.yaml
agenttaint approve approve <confirmation_id> --config ~/agenttaint/agenttaint.yaml
# prints:  approval_token: <token>
```

The same approval is available on the dashboard's Confirmations page. The agent
then retries the identical call with both values; an id without the token is
rejected:

```json
{"to": "partner@corp.example", "subject": "q3", "body": "report",
 "_agenttaint": {"confirmation_id": "<id>", "approval_token": "<token>"}}
```

The approval is bound to the exact arguments and provenance context, expires,
and works once. This is a deliberate change from earlier versions, where the id
alone sufficed.

## 6. Sessions

Each proxy process is one session: it gets a random session id, and the
untrusted content the agent has read is only considered for that session's
calls. To pin a stable id (for example across restarts), pass
`--session-id` to `agenttaint_mcp_proxy.protocol_proxy` or set
`AGENTTAINT_SESSION_ID`. A call that carries a different `session_id` or
`agent_id` in `_agenttaint`, or malformed metadata, is answered with `BLOCK`.

## 7. Watch decisions on the dashboard

```bash
agenttaint dashboard --config ~/agenttaint/agenttaint.yaml   # http://127.0.0.1:8080
```

The dashboard asks once per browser tab for `AGENTTAINT_DASHBOARD_TOKEN` (from
`.env`). It reads the same database as the proxy, so decisions appear live.
Approving on the Confirmations page needs `AGENTTAINT_APPROVER_TOKEN`.

## What it does not do

AgentTaint filters tool calls. It does not stop a model from *saying* something
harmful in its reply, and its reconstruction signals are heuristics, not proofs.
Read [limitations.md](limitations.md) before relying on it.
