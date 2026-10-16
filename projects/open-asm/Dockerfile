# Builds Open-ASM for Anthropic's OSS Scanner.
# Node 22: CI pins node-version 22 and pnpm 10.33.2; Go 1.26: worker/go.mod + CI go-version.
# Network is available during this build only; the scan that follows runs offline, so every
# dependency (pnpm store, Go modules, build outputs) is fetched here. Mirrors CI:
# pnpm install --frozen-lockfile, core-api nest build, worker go build, console tsc+vite build.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    NODE_ENV=development
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Go toolchain matching worker/go.mod (apt's golang is too old, so fetch upstream).
RUN case "$(uname -m)" in \
      x86_64) GOARCH=amd64 ;; \
      aarch64) GOARCH=arm64 ;; \
      *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac \
    && curl -fsSL --retry 3 "https://go.dev/dl/go1.26.0.linux-${GOARCH}.tar.gz" | tar -C /usr/local -xz \
    && /usr/local/go/bin/go version
ENV PATH=/usr/local/go/bin:$PATH

# pnpm version pinned in packageManager field + CI.
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install exactly the lockfile, as CI does.
RUN pnpm install --frozen-lockfile

# Compile each tier. A failing build fails the image (primary_contact gets the log).
RUN pnpm --filter core-api run build
RUN cd /src/worker && go build ./...
RUN pnpm --filter console run build

# Cheap checks that the image works. A failing suite must not abort the build;
# test binaries and build outputs stay in the image for the offline scan.
# core-api: jest unit tests (colocated *.spec.ts, external deps mocked; e2e needs live postgres+redis, not run here).
RUN (timeout 900 pnpm --filter core-api run test || echo "WARNING: core-api jest reported failures")
# worker: go unit tests (Docker-runtime tests skip without a daemon).
RUN cd /src/worker && (timeout 600 go test ./... || echo "WARNING: worker go tests reported failures")
# console: vitest run single pass (Playwright e2e needs browsers + live API, not run here).
RUN (timeout 600 pnpm --filter console run test:run || echo "WARNING: console vitest reported failures")
