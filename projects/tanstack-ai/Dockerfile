# Prepared against TanStack/ai d99f2c6c24f0773ffea24e14a5fa4dedf74bf9bd.
# Build context is the upstream repository, NOT the enrollment repository.
FROM node:24.8.0-bookworm@sha256:82a1d74c5988b72e839ac01c5bf0f7879a8ffd14ae40d7008016bca6ae12852b
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@11.9.0
ENV CI=true NX_DAEMON=false NX_NO_CLOUD=true HUSKY=0 \
    NODE_OPTIONS=--no-node-snapshot
COPY . /src
WORKDIR /src
# Fail if main changes its toolchain; review the Dockerfile instead of silently drifting.
RUN test "$(node -p 'require("./package.json").packageManager.split("+")[0]')" = "pnpm@11.9.0" \
    && test "$(cat .nvmrc)" = "24.8.0"
# Preserve upstream lifecycle-script allowlists and supply-chain policies.
RUN pnpm install --frozen-lockfile
# Explicit projects avoid affected-mode no-op builds on a fresh checkout.
RUN pnpm exec nx run-many --target=build --projects=@tanstack/ai,@tanstack/ai-code-mode,@tanstack/ai-mcp,@tanstack/ai-persistence,@tanstack/ai-isolate-node,@tanstack/ai-isolate-quickjs,@tanstack/ai-sandbox,@tanstack/ai-skills --parallel=2 --skipRemoteCache
# CI=true keeps Vitest noninteractive. Failure must fail the image build.
RUN pnpm exec nx run-many --target=test:lib --projects=@tanstack/ai,@tanstack/ai-code-mode,@tanstack/ai-mcp,@tanstack/ai-persistence,@tanstack/ai-isolate-node,@tanstack/ai-isolate-quickjs,@tanstack/ai-sandbox,@tanstack/ai-skills --parallel=2 --skipRemoteCache
CMD ["bash"]
