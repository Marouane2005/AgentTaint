#!/usr/bin/env bash
# Build the AgentTaint release bundle:
#   dist/agenttaint-<version>/
#     wheels/            all AgentTaint wheels (+ dependencies for this platform)
#     agenttaint.yaml    config template
#     Dockerfile, docker-compose.yml, .env.example
#     docs/              quickstart, configuration, operations, limitations
#     LICENSE, NOTICE, CHANGELOG.md
#   dist/agenttaint-<version>.tar.gz
#
# Requires Python 3.12+ and Node 22+ (to bundle the dashboard UI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(python3 -c 'import tomllib;print(tomllib.load(open("packages/cli/pyproject.toml","rb"))["project"]["version"])')"
OUT="dist/agenttaint-${VERSION}"
PY="${PYTHON:-python3}"

rm -rf "$OUT" "dist/agenttaint-${VERSION}.tar.gz"
mkdir -p "$OUT/wheels" "$OUT/docs"

echo "==> Building dashboard UI (static export)"
(cd apps/dashboard && npm ci --no-audit --no-fund >/dev/null && npm run build:static >/dev/null)
rm -rf packages/api/src/agenttaint_api/ui
cp -R apps/dashboard/out packages/api/src/agenttaint_api/ui

echo "==> Building wheels"
"$PY" -m pip wheel --quiet --wheel-dir "$OUT/wheels" \
  ./packages/core ./packages/provenance ./packages/risk ./packages/policy \
  ./packages/audit ./packages/reconstruction "./packages/agent_sdk[postgres]" \
  ./integrations/mock_email ./packages/mcp_proxy ./packages/api ./packages/cli \
  "psycopg[binary]>=3.2.0"
rm -rf packages/api/src/agenttaint_api/ui

echo "==> Copying deployment files and docs"
cp packages/cli/src/agenttaint_cli/templates/agenttaint.yaml "$OUT/"
cp Dockerfile docker-compose.yml .env.example .dockerignore LICENSE NOTICE CHANGELOG.md "$OUT/"
cp docs/quickstart.md docs/configuration.md docs/operations.md docs/limitations.md "$OUT/docs/"
# The Dockerfile in the bundle installs from wheels/ instead of source.
cp deploy/Dockerfile.wheels "$OUT/Dockerfile"

tar -C dist -czf "dist/agenttaint-${VERSION}.tar.gz" "agenttaint-${VERSION}"
(cd dist && sha256sum "agenttaint-${VERSION}.tar.gz" > "agenttaint-${VERSION}.tar.gz.sha256")
echo "==> dist/agenttaint-${VERSION}.tar.gz"
