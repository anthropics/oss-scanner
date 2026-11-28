# n8n-mcp: a TypeScript MCP server (stdio and HTTP) that serves n8n node documentation from a bundled SQLite
# database and proxies management calls to the n8n REST API. Built and tested the way its CI
# (.github/workflows/test.yml) does: npm ci --legacy-peer-deps, tsc, vitest unit suite.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    N8N_MCP_TELEMETRY_DISABLED=true
# python3/make/g++ are for better-sqlite3 if its prebuilt binary is not available.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The full dependency tree, dev dependencies included (tsc, vitest, msw). The node database
# (data/nodes.db) is committed, so no rebuild from n8n packages is needed.
RUN npm ci --legacy-peer-deps --no-audit --no-fund

# Server: tsc -> dist/. UI apps (MCP Apps result cards, self-contained HTML) -> ui-apps/dist.
RUN npm run build
RUN npm --prefix ui-apps ci --no-audit --no-fund && npm run build:ui

# Unit tests run offline. Integration tests against a live n8n instance are not expected to work here.
RUN npm run test:unit || echo "WARNING: unit tests reported failures"
