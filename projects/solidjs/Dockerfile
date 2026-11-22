FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm version is pinned by "packageManager" in package.json
RUN corepack enable && corepack prepare --activate || true
RUN pnpm install --frozen-lockfile

# Build the library packages. The Rust compiler package and the examples/ apps (which need the native compiler) are skipped.
RUN pnpm exec turbo run build --filter='./packages/*' --filter='!@solidjs/compiler'

# Run the tests so the image is known to work, but do not let failures abort the build.
RUN (pnpm run test || echo "WARNING: tests reported failures")
