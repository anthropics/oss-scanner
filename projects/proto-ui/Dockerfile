# Static preparation only: this image has not yet been built or tested.
# Scanner contract: the project checkout is the build context and lives at /src.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=1 \
    HUSKY=0 \
    ASTRO_TELEMETRY_DISABLED=1 \
    CHROME_PATH=/usr/bin/chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate
COPY . /src
WORKDIR /src
RUN corepack pnpm@10.32.1 install --frozen-lockfile
RUN corepack pnpm@10.32.1 build:packages
RUN corepack pnpm@10.32.1 docs:build
# Build failures are fatal. Run the documented tests in the resulting image
# with Internet access disabled; do not treat image construction as a test pass.
