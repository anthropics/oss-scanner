# GreenTunnel v3: an npm workspace with the engine + CLI (packages/cli) and an Electron desktop app (apps/desktop).
# Debian rather than the project's own alpine image, so the scanner's debugging tools install.
FROM node:24-bookworm

# Typechecking and bundling the desktop app need Electron's typings, not its ~150 MB binary (as in the project's CI).
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
    CI=1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every workspace's dependencies, dev ones included, so the build, tests and lint all work offline.
RUN npm ci

# tsc --build for packages/cli (dist/ with source maps), then electron-vite build for apps/desktop (out/).
RUN npm run build

# The CLI is then runnable offline as: node packages/cli/dist/main.js --no-system-proxy --port 8000
RUN node packages/cli/dist/main.js --help

# Cheap checks, so you know the image works; a failure does not abort the build.
RUN npm test || echo "WARNING: vitest reported failures"
RUN npm run typecheck || echo "WARNING: typecheck reported failures"
