# Jaeger UI: pnpm monorepo (packages/jaeger-ui, packages/plexus). Node version from .nvmrc (24).
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    HUSKY=0 \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable pnpm

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm version comes from packageManager in package.json (pnpm@12.8.2) via corepack.
# preinstall runs `npx only-allow pnpm` and rejects npm.
RUN corepack pnpm install --frozen-lockfile
RUN corepack pnpm run build

# Unit tests (vitest); failures are logged, not fatal.
RUN corepack pnpm run test || echo "WARNING: unit tests reported failures"
