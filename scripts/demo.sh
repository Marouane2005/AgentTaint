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
echo "Open the dashboard, click \"Seed demo session\", then inspect"
echo "Overview / Provenance / Gateway. Press Ctrl-C to stop."
echo

wait
