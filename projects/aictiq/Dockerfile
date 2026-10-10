FROM mcr.microsoft.com/dotnet/sdk:10.0

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

# Node 24 (the version CI uses). pnpm is pinned by each package.json's packageManager field.
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g corepack@latest \
    && corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Backend: API, Workers and shared modules (.NET 10). Building the solution also restores and
# compiles the integration tests, so their packages are cached for offline use.
RUN dotnet build Aictiq.slnx --configuration Release -p:SkipWebBuild=true

# Web SPA (Vue + Vite), served by the API from wwwroot in production.
RUN cd frontend-vue && pnpm install --frozen-lockfile && pnpm run build
RUN cd frontend-vue && (pnpm test || echo "WARNING: web unit tests reported failures")

# CLI, factory runner and MCP client (TypeScript).
RUN cd cli && pnpm install --frozen-lockfile && pnpm run build
RUN cd cli && (pnpm test || echo "WARNING: CLI unit tests reported failures")

# The backend integration tests (backend/tests/IntegrationTests) start Postgres and Garage with
# Testcontainers, which needs a Docker daemon, so they are built above but not run here.
