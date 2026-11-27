# assistant-ui (https://github.com/assistant-ui/assistant-ui), a pnpm and Turborepo monorepo. The library packages
# under packages/ are built and their unit tests run; apps/, examples/ and templates/ are installed but not built.
# Everything the build and the tests need is installed here, from the committed pnpm-lock.yaml, before the network
# is removed.
FROM node:26-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    TURBO_TELEMETRY_DISABLED=1 \
    DO_NOT_TRACK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm at the version `packageManager` pins in package.json. Node 26 no longer bundles corepack.
RUN npm install --global "$(node -p "require('./package.json').packageManager")"

RUN pnpm install --frozen-lockfile

# Build every package under packages/ (dist/ in each), as CI's package build does.
RUN pnpm turbo build --filter='./packages/*'

# Unit tests (vitest, colocated with sources as packages/*/src/**/*.test.ts(x)). --continue runs every package's
# tests after one fails; a failing test must not abort the build. One test is known to fail in this image: a variants
# server test expects a chmod 000 directory to be unreadable, which root can still read.
RUN pnpm turbo test --continue --filter='./packages/*' || echo "WARNING: unit tests reported failures"
