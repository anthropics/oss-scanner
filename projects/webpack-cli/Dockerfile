# webpack-cli: an npm workspaces monorepo (packages/webpack-cli, packages/create-webpack-app) with a
# lockfileVersion 3 package-lock.json. Mirrors the `test` job in .github/workflows/nodejs.yml: `npm ci
# --ignore-scripts`, compile the TypeScript sources with `npm run build`, then run the Jest suite.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# The package-manager detection tests in test/api look for pnpm on PATH, as in CI.
RUN npm install -g pnpm@10 || echo "WARNING: could not install pnpm"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci --ignore-scripts --no-audit --no-fund

RUN npm run build -- --sourceMap true

# Smoke test, so a broken image is visible in the build log without failing the build. The full suite
# (`npm run test:base -- --ci`) is listed in threat_model.md; `npm test` would also run build and lint.
RUN node packages/webpack-cli/bin/cli.js --version \
    && npm run test:base -- --ci test/build/basic test/version \
    || echo "WARNING: webpack-cli smoke tests reported failures"
