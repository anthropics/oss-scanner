# Prepared against TanStack/workflow b9287174b44424059895a0ed834b18ce50e0484a.
# Build context is the upstream repository, NOT the enrollment repository.
FROM node:24.8.0-bookworm@sha256:82a1d74c5988b72e839ac01c5bf0f7879a8ffd14ae40d7008016bca6ae12852b
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@10.33.2
ENV CI=true NX_DAEMON=false NX_NO_CLOUD=true HUSKY=0
COPY . /src
WORKDIR /src
# Fail if main changes its toolchain; review the Dockerfile instead of silently drifting.
RUN test "$(node -p 'require("./package.json").packageManager.split("+")[0]')" = "pnpm@10.33.2" \
    && test "$(cat .nvmrc)" = "24.8.0"
# Preserve upstream lifecycle-script allowlists and supply-chain policies.
RUN pnpm install --frozen-lockfile
# Explicit projects avoid affected-mode no-op builds on a fresh checkout.
RUN pnpm exec nx run-many --target=build --projects=@tanstack/workflow-core,@tanstack/workflow-runtime,@tanstack/workflow-vercel,@tanstack/workflow-netlify,@tanstack/workflow-cloudflare,@tanstack/workflow-railway,@tanstack/workflow-store-drizzle-postgres,@tanstack/workflow-store-cloudflare-d1 --parallel=2 --skipRemoteCache
# CI=true keeps Vitest noninteractive. Failure must fail the image build.
RUN pnpm exec nx run-many --target=test:lib --projects=@tanstack/workflow-core,@tanstack/workflow-runtime,@tanstack/workflow-vercel,@tanstack/workflow-netlify,@tanstack/workflow-cloudflare,@tanstack/workflow-railway,@tanstack/workflow-store-drizzle-postgres,@tanstack/workflow-store-cloudflare-d1 --parallel=2 --skipRemoteCache
CMD ["bash"]
