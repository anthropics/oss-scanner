FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=1 \
    TURBO_TELEMETRY_DISABLED=1 \
    DO_NOT_TRACK=1 \
    NODE_OPTIONS=--max-old-space-size=8192

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential python3 git ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global pnpm@9.15.0 --ignore-scripts

COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile --filter '!@bb/mobile'
RUN pnpm run build
RUN pnpm exec turbo run build:types --filter=@get-bb/plugin-sdk

RUN pnpm exec turbo run test \
      --filter=@bb/server --filter=@bb/host-daemon --filter=@bb/db --filter=@bb/host-workspace \
      --concurrency=2 --continue \
    || echo "WARNING: some tests failed"

CMD ["bash"]
