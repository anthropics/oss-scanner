# Folo: a pnpm + Turborepo monorepo (Electron desktop app, Expo mobile app, web app, SSR server and shared packages).
# Mirrors .github/workflows/lint.yml and build-desktop.yml: install with the frozen lockfile (its postinstall builds
# packages/), build the Electron main, preload and renderer bundles, the web app and the SSR server, then run every
# workspace's tests as a smoke test.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    VITE_WEB_URL=https://app.folo.is \
    VITE_API_URL=https://api.follow.is
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential zstd \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm comes from the packageManager pin in package.json; `corepack install` caches it for offline use.
RUN corepack install && pnpm install --frozen-lockfile --child-concurrency=1

# Electron main process, preload script and renderer (apps/desktop/dist), as the desktop release build does.
RUN NODE_OPTIONS=--max-old-space-size=16384 pnpm --filter Folo run build:electron-vite
# The web app (apps/desktop/out/web) and the SSR server (apps/ssr/dist), as CI builds them, and the main process's
# type declarations, which the renderer's type-checked tests import.
RUN NODE_OPTIONS=--max-old-space-size=16384 pnpm exec turbo run Folo#build:web @follow/ssr#build @follow/electron-main#build

# Smoke test, so a broken image is visible in the build log without failing the build. zstd is for the OTA release
# script's tests.
RUN pnpm exec turbo run test --continue || echo "WARNING: some workspace tests reported failures"
