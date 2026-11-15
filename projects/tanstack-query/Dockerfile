# Prepared against TanStack/query 90e331decc7f68e43a93f10def05f83d26c4e26c.
# Build context is the upstream repository, NOT the enrollment repository.
FROM node:24.21.0-bookworm@sha256:3d27e5c11e5786e309ec3e03f93ae536eb36e6e5eb3714d5eb3300a36157add0
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@12.4.2
ENV CI=true NX_DAEMON=false NX_NO_CLOUD=true HUSKY=0
COPY . /src
WORKDIR /src
# Fail if main changes its toolchain; review the Dockerfile instead of silently drifting.
RUN test "$(node -p 'require("./package.json").packageManager.split("+")[0]')" = "pnpm@12.4.2" \
    && test "$(cat .nvmrc)" = "24.21.0"
# Preserve upstream lifecycle-script allowlists and supply-chain policies.
RUN pnpm install --frozen-lockfile
# Explicit projects avoid affected-mode no-op builds on a fresh checkout.
RUN pnpm exec nx run-many --target=build --projects=@tanstack/query-core,@tanstack/react-query,@tanstack/react-query-next-experimental --parallel=2 --skipRemoteCache
# CI=true keeps Vitest noninteractive. Failure must fail the image build.
RUN pnpm exec nx run-many --target=test:lib --projects=@tanstack/query-core,@tanstack/react-query --parallel=2 --skipRemoteCache
CMD ["bash"]
