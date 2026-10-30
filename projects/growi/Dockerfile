# GROWI (https://github.com/growilabs/growi) for OSS Scanner.
# Build context is the GROWI checkout. Network is available only during this build, so everything the
# tests and a local GROWI server need (node_modules, Prisma engine, a mongod binary) is fetched here.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_OPTIONS="--max-old-space-size=8192" \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    TURBO_TELEMETRY_DISABLED=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    MONGOMS_DISTRO=ubuntu-22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential curl libcurl4 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Use the pnpm version pinned by "packageManager" in package.json; corepack caches it for offline use.
RUN corepack enable && pnpm --version

# Install the whole workspace (dev dependencies included, so vitest/turbo work offline).
# apps/app's postinstall runs `prisma generate`, which downloads the Prisma query engine.
RUN pnpm install --frozen-lockfile

# Build the main app (Next.js client + TypeScript server) and the workspace packages it depends on.
RUN pnpm exec turbo run build --filter @growi/app

# Pre-download the mongod binary that the integration tests start via mongodb-memory-server
# (version from apps/app/.env.test; downloadDir from apps/app/test/setup/mongo/utils.ts).
# MongoDB 6.0 has no Debian 12 build, so MONGOMS_DISTRO (above) selects the Ubuntu 22.04 build,
# which runs on bookworm. The binary is also linked as /usr/local/bin/mongod for running GROWI itself.
RUN cd /src/apps/app \
    && node -e "require('mongodb-memory-server-core').MongoBinary.getPath({version:'6.0.9',downloadDir:'node_modules/.cache/mongodb-binaries'}).then(p=>console.log(p))" \
    && ln -sf "$(ls -d /src/apps/app/node_modules/.cache/mongodb-binaries/mongod-* | head -1)" /usr/local/bin/mongod \
    && mongod --version

# Smoke test: run the app's unit tests so a broken image shows up in the log, without failing the build.
RUN cd /src/apps/app \
    && (timeout 1200 pnpm run test:unit || echo "WARNING: apps/app unit tests reported failures")
