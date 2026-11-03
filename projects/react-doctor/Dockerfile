FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    TURBO_TELEMETRY_DISABLED=1 \
    DO_NOT_TRACK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# The pnpm version pinned by `packageManager` in package.json.
RUN npm install -g pnpm@10.29.1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same steps as CI (.github/workflows/ci.yml): install, then build every package under packages/.
RUN pnpm install --frozen-lockfile
RUN pnpm build

# Unit tests (vitest through turbo) for the CLI, core engine, API, both lint plugins, the fuzz harness and the evals.
# --continue runs every package's tests after one fails. Three tests are known to fail in this image: two in
# react-doctor need the score API, and one in core expects a chmod 000 file to be unreadable, which root can still read.
RUN pnpm test --continue --concurrency=1 || echo "WARNING: tests reported failures"
