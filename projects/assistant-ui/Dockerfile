FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    TURBO_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile

# Build the published library packages (apps, docs and examples are not needed for the audit).
RUN pnpm turbo build --concurrency=4 --filter='./packages/*'

# Unit tests (vitest), colocated with sources under packages/*/src.
RUN pnpm turbo test --concurrency=4 --filter='./packages/*' || echo "WARNING: unit tests reported failures"
