FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# ffmpeg backs the audio tools; Chromium (below) backs the browser-render tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same installs as production (Dockerfile, Dockerfile.mcp): the server, then the MCP package.
# tollbooth/ and client/ resolve their dependencies from the root node_modules.
RUN npm ci --omit=dev && npx playwright install --with-deps chromium
RUN npm ci --omit=dev --prefix mcp

# Smoke: the server boots in free mode (no keys, no payment rails) and answers /health.
RUN (FREE_MODE=true PORT=3000 node src/server.js > /tmp/boot.log 2>&1 &) \
    && for i in $(seq 1 60); do curl -fsS http://127.0.0.1:3000/health >/dev/null && break; sleep 1; done \
    && (curl -fsS http://127.0.0.1:3000/health | head -c 200; echo) \
    || (echo "WARNING: free-mode boot did not answer /health"; tail -40 /tmp/boot.log)

# Offline unit suites. Suites that need upstream keys, Postgres, Redis or the network are not run here.
RUN npm test || echo "WARNING: npm test reported failures"
RUN (cd tollbooth && node test.js && node edge.test.js && node features.test.js) || echo "WARNING: tollbooth tests reported failures"
RUN for t in test-sales-ledger test-refund-ledger test-credits test-idempotency test-memory test-external-spend-guard test-pow-shared-replay; do \
      if [ -f scripts/$t.js ]; then node scripts/$t.js > /tmp/$t.log 2>&1 && echo "ok $t" || echo "WARNING: $t failed"; fi; \
    done
