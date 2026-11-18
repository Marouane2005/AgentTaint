# syntax=docker/dockerfile:1
# AgentTaint 1.0 production image (built from source).
# One image, two roles:
#   agenttaint dashboard   control-plane API + dashboard UI on :8080
#   agenttaint proxy       MCP proxy on stdio in front of your MCP server
# Secrets come only from the environment; nothing secret is baked in.

FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY apps/dashboard/package.json apps/dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/dashboard ./
RUN npm run build:static

FROM python:3.12-slim AS wheels
WORKDIR /src
COPY packages ./packages
COPY integrations ./integrations
COPY --from=ui /ui/out ./packages/api/src/agenttaint_api/ui
RUN pip wheel --no-cache-dir --wheel-dir /wheels \
      ./packages/core ./packages/provenance ./packages/risk ./packages/policy \
      ./packages/audit ./packages/reconstruction "./packages/agent_sdk[postgres]" \
      ./integrations/mock_email ./packages/mcp_proxy ./packages/api ./packages/cli \
      "psycopg[binary]>=3.2.0"

FROM python:3.12-slim
# Node lets the proxy launch npx-based MCP servers; set WITH_NODE=0 to omit it.
ARG WITH_NODE=1
RUN if [ "$WITH_NODE" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends nodejs npm \
      && rm -rf /var/lib/apt/lists/*; fi \
 && useradd --system --uid 10001 --create-home --home-dir /home/agenttaint agenttaint
COPY --from=wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels \
      agenttaint "agenttaint-agent-sdk[postgres]" \
 && rm -rf /wheels
WORKDIR /home/agenttaint
USER 10001
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENTTAINT_API_AUTH=required
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4)" || exit 1
ENTRYPOINT ["agenttaint"]
CMD ["dashboard", "--config", "/etc/agenttaint/agenttaint.yaml", "--host", "0.0.0.0"]
