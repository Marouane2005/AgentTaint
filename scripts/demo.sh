#!/usr/bin/env bash
# One-command local demo: API control plane + Next.js dashboard.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8080}"
DASH_PORT="${DASH_PORT:-3000}"
PYTHON="${PYTHON:-python3}"

echo "==> Installing Python packages (if needed)"
make install >/tmp/agenttaint-demo-install.log 2>&1 || {
  echo "make install failed; see /tmp/agenttaint-demo-install.log" >&2
  exit 1
}

echo "==> Installing dashboard deps (if needed)"
make dashboard-install >/tmp/agenttaint-demo-dash-install.log 2>&1 || {
  echo "dashboard install failed; see /tmp/agenttaint-demo-dash-install.log" >&2
  exit 1
}

mkdir -p .agenttaint/demo

# Confirmation secret: there is no built-in default. Generate a random one for
# this demo run unless the operator already exported one.
if [[ -z "${AGENTTAINT_CONFIRM_SECRET:-}" ]]; then
  AGENTTAINT_CONFIRM_SECRET="$("$PYTHON" -c 'import secrets; print(secrets.token_hex(32))')"
  export AGENTTAINT_CONFIRM_SECRET
  echo "==> Generated a random AGENTTAINT_CONFIRM_SECRET for this demo run"
fi
# Operator token for the out-of-band approval endpoints (/api/v1/confirmations).
if [[ -z "${AGENTTAINT_DASHBOARD_TOKEN:-}" ]]; then
  AGENTTAINT_DASHBOARD_TOKEN="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(24))')"
  export AGENTTAINT_DASHBOARD_TOKEN
fi
export AGENTTAINT_SECURITY_DB_URL="${AGENTTAINT_SECURITY_DB_URL:-sqlite+pysqlite:///$ROOT/.agenttaint/demo/security.db}"
# Operator credentials for a second terminal (file is git-ignored, mode 0600).
OPERATOR_ENV=".agenttaint/demo/operator.env"
(
  umask 077
  {
    printf 'export AGENTTAINT_CONFIRM_SECRET=%q\n' "$AGENTTAINT_CONFIRM_SECRET"
    printf 'export AGENTTAINT_DASHBOARD_TOKEN=%q\n' "$AGENTTAINT_DASHBOARD_TOKEN"
    printf 'export AGENTTAINT_SECURITY_DB_URL=%q\n' "$AGENTTAINT_SECURITY_DB_URL"
  } >"$OPERATOR_ENV"
)
API_PID_FILE=".agenttaint/demo/api.pid"
DASH_PID_FILE=".agenttaint/demo/dashboard.pid"

cleanup() {
  if [[ -f "$API_PID_FILE" ]]; then
    kill "$(cat "$API_PID_FILE")" 2>/dev/null || true
    rm -f "$API_PID_FILE"
  fi
  if [[ -f "$DASH_PID_FILE" ]]; then
    kill "$(cat "$DASH_PID_FILE")" 2>/dev/null || true
    rm -f "$DASH_PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

echo "==> Starting API on http://127.0.0.1:${API_PORT}"
HOST=127.0.0.1 PORT="$API_PORT" AGENTTAINT_API_AUTH=off \
  "$PYTHON" -m agenttaint_api >/tmp/agenttaint-demo-api.log 2>&1 &
echo $! >"$API_PID_FILE"

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${API_PORT}/api/v1/health" >/dev/null; then
    break
  fi
  sleep 0.25
done
curl -sf "http://127.0.0.1:${API_PORT}/api/v1/health" >/dev/null

echo "==> Starting dashboard on http://127.0.0.1:${DASH_PORT}"
(
  cd apps/dashboard
  AGENTTAINT_API_ORIGIN="http://127.0.0.1:${API_PORT}" \
    npm run dev -- --port "$DASH_PORT" --hostname 127.0.0.1
) >/tmp/agenttaint-demo-dashboard.log 2>&1 &
echo $! >"$DASH_PID_FILE"

echo
echo "AgentTaint local demo is running."
echo "  Dashboard: http://127.0.0.1:${DASH_PORT}"
echo "  API:       http://127.0.0.1:${API_PORT}/api/v1/health"
echo "  Logs:      /tmp/agenttaint-demo-{api,dashboard}.log"
echo
echo "Out-of-band approvals (the agent cannot approve its own CONFIRMs):"
echo "  source ${OPERATOR_ENV}   # in a second terminal"
echo "  python3 -m agenttaint_agent_sdk.confirm_cli list"
echo "  curl -H \"X-AgentTaint-Token: \$AGENTTAINT_DASHBOARD_TOKEN\" http://127.0.0.1:${API_PORT}/api/v1/confirmations"
echo "  (secrets are not printed; they live in ${OPERATOR_ENV})"
echo
echo "Open the dashboard, click \"Seed demo session\", then inspect"
echo "Overview / Provenance / Gateway. Press Ctrl-C to stop."
echo

wait
