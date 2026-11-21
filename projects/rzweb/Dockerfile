# OSS Scanner build of RzWeb (https://github.com/IndAlok/rzweb).
#
# RzWeb is a React + TypeScript frontend that runs Rizin, compiled to WebAssembly by rzwasi, inside a Web Worker.
# This repo has no native code. The image mirrors .github/workflows/ci.yml and also fetches, while the network is up:
#   /opt/rzwasi-dist   the published rizin.js + rizin.wasm pair (also copied to public/rzwasi so the built app
#                      and the MCP server work offline)
#   /opt/rzwasi-src    the rzwasi build layer source (Emscripten patches and the rzweb_* session API), for reading
#   Chromium for Playwright, so the built app can be driven headless with no network.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    RZWEB_WASM_DIR=/opt/rzwasi-dist \
    RZWEB_CONTEXT_DIR=/tmp/rzweb-contexts \
    NODE_PATH=/usr/local/lib/node_modules

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 file binutils \
    && rm -rf /var/lib/apt/lists/*

# Published WASM core and the rzwasi source it was built from.
RUN mkdir -p /opt/rzwasi-dist \
    && curl -fsSL -o /opt/rzwasi-dist/rizin.js https://indalok.github.io/rzwasi/rizin.js \
    && curl -fsSL -o /opt/rzwasi-dist/rizin.wasm https://indalok.github.io/rzwasi/rizin.wasm \
    && (curl -fsSL https://indalok.github.io/rzwasi/VERSION -o /opt/rzwasi-dist/VERSION || echo unknown > /opt/rzwasi-dist/VERSION) \
    && git clone --depth 1 https://github.com/IndAlok/rzwasi /opt/rzwasi-src

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Frontend: same steps as CI, but point the worker at a local copy of the WASM pair so the build runs offline.
RUN npm ci
RUN mkdir -p public/rzwasi && cp /opt/rzwasi-dist/rizin.js /opt/rzwasi-dist/rizin.wasm public/rzwasi/ \
    && cp /opt/rzwasi-dist/VERSION public/VERSION
RUN VITE_RIZIN_VERSION="$(cat /opt/rzwasi-dist/VERSION)" VITE_WASM_BASE_URL=/rzwasi npm run build

# Local MCP server (mcp/) and the hosted Worker sketch (hosted/, never deployed).
RUN cd mcp && npm ci && npm run build
RUN cd hosted && npm ci

# Headless Chromium for driving the built app (serve it with: npx vite preview --port 4173 --strictPort).
RUN npm install -g playwright@1 && playwright install --with-deps chromium

# Cheap checks so you know the image works. Failures are logged, not fatal.
RUN npm run lint || echo "WARNING: lint reported problems"
RUN npm run typecheck || echo "WARNING: typecheck reported problems"
RUN npm test || echo "WARNING: vitest reported failures"
RUN (cd mcp && npx tsc --noEmit) || echo "WARNING: mcp typecheck reported problems"
RUN (cd hosted && npx tsc --noEmit) || echo "WARNING: hosted typecheck reported problems"
