# Prepared against TanStack/db 31dad2dd3b835310612747c5af457561aa77e997.
# Build context is the upstream repository, NOT the enrollment repository.
FROM node:24.8.0-bookworm@sha256:82a1d74c5988b72e839ac01c5bf0f7879a8ffd14ae40d7008016bca6ae12852b
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ pkg-config sqlite3 \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@11.1.0
ENV CI=true NX_DAEMON=false NX_NO_CLOUD=true HUSKY=0
COPY . /src
WORKDIR /src
# Fail if main changes its toolchain; review the Dockerfile instead of silently drifting.
RUN test "$(node -p 'require("./package.json").packageManager.split("+")[0]')" = "pnpm@11.1.0" \
    && test "$(cat .nvmrc)" = "24.8.0"
# Preserve upstream lifecycle-script allowlists and supply-chain policies.
RUN pnpm install --frozen-lockfile
# Explicit projects avoid affected-mode no-op builds on a fresh checkout.
RUN pnpm --filter @tanstack/node-db-sqlite-persistence... --filter @tanstack/cloudflare-durable-objects-db-sqlite-persistence... run build
# CI=true keeps Vitest noninteractive. Failure must fail the image build.
RUN pnpm --filter @tanstack/db-sqlite-persistence-core --filter @tanstack/node-db-sqlite-persistence --filter @tanstack/cloudflare-durable-objects-db-sqlite-persistence run test
CMD ["bash"]
