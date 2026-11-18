# Quickstart: put AgentTaint in front of any MCP server

AgentTaint runs as a **stdio MCP proxy**. Your MCP client launches
`agenttaint proxy` instead of the server; the proxy launches the real server as a
child process and forwards only the tool calls its policy allows. Calls it does
not allow are answered with `BLOCK`, or held as `CONFIRM` until a person approves
them out of band (`agenttaint approve` or the dashboard's Confirmations page).

Time needed: about 10 minutes. Requirements: Python 3.12+, and Node.js if the
MCP server you protect is an `npx` package.

## 1. Install

Pro customers receive `agenttaint-1.0.0.tar.gz` (and a `.sha256` file).

```bash
sha256sum -c agenttaint-1.0.0.tar.gz.sha256
tar xzf agenttaint-1.0.0.tar.gz && cd agenttaint-1.0.0
python3 -m venv ~/.agenttaint-venv
~/.agenttaint-venv/bin/pip install --no-index --find-links wheels agenttaint
~/.agenttaint-venv/bin/agenttaint --version          # agenttaint 1.0.0
```

`--no-index` makes pip install only from the bundled wheels, so nothing is
fetched from a public index under the same names. The bundled dependency wheels
target Linux x86_64 / CPython 3.12; on other platforms drop `--no-index` and pip
fetches the third-party dependencies (FastAPI, cedarpy, ...) from PyPI while the
AgentTaint wheels still come from `wheels/`.

From a source checkout instead: `pip install -e packages/cli` after `make install`.

## 2. Create a configuration

```bash
mkdir -p ~/agenttaint && cd ~/agenttaint
agenttaint init .
```

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

### Claude Desktop

`claude_desktop_config.json` (Settings → Developer → Edit Config):

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

Remove the server's original entry so the client cannot call it directly.

### IDE MCP clients

Most IDE clients use the same shape. A workspace `mcp.json` example:

```json
{
  "servers": {
    "files-protected": {
      "type": "stdio",
      "command": "/home/you/.agenttaint-venv/bin/agenttaint",
      "args": ["proxy", "--config", "/home/you/agenttaint/agenttaint.yaml"]
    }
  }
}
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

## 5. Watch decisions and approve held calls

```bash
agenttaint dashboard --config ~/agenttaint/agenttaint.yaml   # http://127.0.0.1:8080
```

The dashboard asks once per browser tab for `AGENTTAINT_DASHBOARD_TOKEN` (from
`.env`). It reads the same database as the proxy, so decisions appear live.

When a call is held, the agent sees a `CONFIRM` error with a confirmation id.
Approve from a terminal the agent cannot reach:

```bash
agenttaint approve --config ~/agenttaint/agenttaint.yaml list
agenttaint approve --config ~/agenttaint/agenttaint.yaml show <id>
agenttaint approve --config ~/agenttaint/agenttaint.yaml approve <id>
```

or on the dashboard's Confirmations page with `AGENTTAINT_APPROVER_TOKEN`. The
agent then retries the exact same call with the confirmation id; an approval is
bound to those exact arguments and works once.

## What it does not do

AgentTaint filters tool calls. It does not stop a model from *saying* something
harmful in its reply, and its reconstruction signals are heuristics, not proofs.
Read [limitations.md](limitations.md) before relying on it.
