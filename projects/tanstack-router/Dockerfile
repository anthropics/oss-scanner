# Prepared against TanStack/router ed5577593a749b8c7193cc7b5d945fd084bfac2f.
# Build context is the upstream repository, NOT the enrollment repository.
FROM node:26.10.0-bookworm@sha256:e6cfc3514df35d1cb534e83f9279a242ad6e578692ab7b56d73dadcc7c4354a0
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@11.21.0
# Keep the Vite test listener and fetch on the same localhost address family.
ENV CI=true NX_DAEMON=false NX_NO_CLOUD=true HUSKY=0 \
    NODE_OPTIONS=--dns-result-order=ipv4first
COPY . /src
WORKDIR /src
# Fail if main changes its toolchain; review the Dockerfile instead of silently drifting.
RUN test "$(node -p 'require("./package.json").packageManager.split("+")[0]')" = "pnpm@11.21.0" \
    && test "$(cat .nvmrc)" = "26.10.0"
# Preserve upstream lifecycle-script allowlists and supply-chain policies.
RUN pnpm install --frozen-lockfile
# Explicit projects avoid affected-mode no-op builds on a fresh checkout.
RUN pnpm exec nx run-many --target=build --projects=@tanstack/start-server-core,@tanstack/start-client-core,@tanstack/router-core,@tanstack/start-plugin-core,@tanstack/router-ssr-query-core --parallel=2 --skipRemoteCache
# CI=true keeps Vitest noninteractive. Failure must fail the image build.
RUN pnpm exec nx run-many --target=test:unit --projects=@tanstack/start-server-core,@tanstack/start-client-core,@tanstack/router-core,@tanstack/start-plugin-core,@tanstack/router-ssr-query-core --parallel=2 --skipRemoteCache
CMD ["bash"]
