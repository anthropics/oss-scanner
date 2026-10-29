# Appflare: a pnpm 10 + Turborepo monorepo of TypeScript Cloudflare Workers (manager, hosted installer, sandbox
# Worker, docs site) and the Node packages they share (schema, pack, cf-api, cli). Mirrors .github/workflows/ci.yml:
# install with a frozen lockfile, build every package, then run the cheap tests as a smoke test.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    TURBO_TELEMETRY_DISABLED=1 \
    WRANGLER_SEND_METRICS=false
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm at the exact version package.json's packageManager field pins.
RUN corepack enable pnpm && corepack install

# Install scripts are allowed only for esbuild, biome and workerd (pnpm-workspace.yaml). workerd's is what fetches
# the binary the Workers test pool (@cloudflare/vitest-pool-workers) runs, so the tests work offline afterwards.
RUN pnpm install --frozen-lockfile

# Build every package and app: tsdown for the packages, vite for the manager and docs Workers.
RUN pnpm build

# Smoke test, so a broken image is visible in the build log without failing the build. The manager's suite is the
# longest (CI shards it three ways); run it with `pnpm exec turbo run test --filter=@appflare/manager`.
RUN pnpm exec turbo run test --continue --filter='!@appflare/manager' || echo "WARNING: tests reported failures"
