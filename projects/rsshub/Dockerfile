# RSSHub: a single-package pnpm repository (TypeScript on Node.js, served with Hono). Mirrors the `vitest` job in
# .github/workflows/test.yml: install with the frozen lockfile, rebuild native dependencies, fetch the Chromium that
# Patchright-based routes drive, build the route registry and the server bundle, then run the unit tests against a
# local Redis as a smoke test.
FROM node:24-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential redis-server \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm comes from the packageManager pin in package.json; `corepack install` caches it for offline use.
RUN corepack install && pnpm install --frozen-lockfile && pnpm rb

# Chromium (and its system libraries) for the routes that render pages with Patchright, fetched while the network
# is up. Optional: most routes never start a browser.
RUN pnpm exec patchright install --with-deps chromium || echo "WARNING: could not install Chromium for Patchright"

# Build the route registry (assets/build/) and the server bundle (dist/), as `pnpm build` does upstream.
RUN pnpm build

# Smoke test, so a broken image is visible in the build log without failing the build. The tests mock upstream
# sites with msw, so they do not need the network.
RUN redis-server --daemonize yes \
    && (REDIS_URL=redis://localhost:6379/ pnpm vitest run || echo "WARNING: vitest reported failures"); \
    redis-cli shutdown nosave || true
