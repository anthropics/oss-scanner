# OSS Scanner build of tldraw.
#
# The scanner builds this with the tldraw checkout as the build context, so `COPY . /src` puts it at /src.
# Network access exists only while this file builds, so everything the tests need is fetched here: the pnpm
# workspace dependencies and a Playwright Chromium for driving the examples app in a real browser.
#
# What is built:
#   packages/*/dist-*   the published SDK packages (tldraw, @tldraw/editor, @tldraw/sync-core, ...)
#   .tsbuild*/           the type declarations made by `pnpm typecheck`
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    TURBO_TELEMETRY_DISABLED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# build-essential, python3 and libsecret are for the native modules pnpm-workspace.yaml allows to build
# (better-sqlite3, sqlite3, keytar, ...) when no prebuilt binary matches.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential libsecret-1-dev jq \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same steps as CI (.github/actions/setup and .github/workflows/checks.yml). corepack fetches the pnpm
# version pinned in package.json's packageManager field.
RUN npm i -g corepack && corepack enable && corepack install
RUN pnpm install --frozen-lockfile
RUN pnpm build-package
RUN pnpm typecheck

# Chromium (with its system libraries) for the Playwright e2e tests in apps/examples/e2e, and for checking
# whether a document or paste executes script in the examples app (`pnpm dev`, http://localhost:5420).
RUN cd apps/examples && pnpm exec playwright install --with-deps chromium

# Unit and integration tests (vitest, every workspace). Do not let a failing test abort the build.
RUN pnpm test-ci || echo "WARNING: vitest reported failures"
