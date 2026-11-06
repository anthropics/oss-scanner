# Match Openship's Bun pin, Node engine requirement and Actions Go toolchain.
FROM oven/bun:1.3.14 AS bun
FROM golang:1.26.9-bookworm AS go
FROM node:22-bookworm

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl git openssh-client openssl \
        pkg-config python3 ripgrep rsync lua5.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=go /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    NEXT_TELEMETRY_DISABLED=1 \
    ELECTRON_SKIP_BINARY_DOWNLOAD=1

# tools/check supplies a clean public checkout, never a maintainer's worktree.
# Keep source, development dependencies, migrations and test fixtures available.
COPY . /src
WORKDIR /src
RUN bun install --frozen-lockfile --linker hoisted

# The API build stages all supported Actions runner binaries. Keep the Go
# module cache as well so runner tests and rebuilds can run without a network.
RUN bun run --cwd packages/actions-runner build
RUN bun run build --concurrency=1

# Cheap smoke coverage; retain failures for review without preventing analysis.
RUN cd /src/apps/api \
    && (bun run test test/lib/active-deployment-ownership.test.ts \
        test/modules/cloud-ingest-isolation.test.ts \
        test/lib/edge-host-isolation.test.ts --maxWorkers=2 \
        || echo "WARNING: API smoke tests reported failures")

CMD ["bash"]
