# x402: a monorepo with a TypeScript, Go, Python and Java SDK and the EVM contracts. Each part is built the way
# its CI workflow builds it (.github/workflows: unit_tests.yml, check_go.yml, check_python.yml, java.yml), and
# every dependency is fetched here so the tests run later with no network.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential pkg-config python3 openjdk-17-jdk-headless maven \
    && rm -rf /var/lib/apt/lists/*

# Toolchains at the versions CI uses: pnpm 11.1.1, Go 1.26.10, uv with Python 3.13, Foundry.
RUN npm install -g pnpm@11.1.1
COPY --from=golang:1.26.10-bookworm /usr/local/go /usr/local/go
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
ENV FOUNDRY_DIR=/opt/foundry \
    UV_PYTHON=3.13 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    GOTOOLCHAIN=local \
    PATH=/usr/local/go/bin:/root/go/bin:/opt/foundry/bin:$PATH
RUN curl -fsSL https://foundry.paradigm.xyz | bash && foundryup

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner clones only the top-level repository; the contracts need forge-std, OpenZeppelin and Permit2.
# Not --recursive: nothing here imports from the submodules' own submodules, and they are slow to fetch.
RUN git -c credential.helper= submodule update --init --depth 1

# TypeScript: the published packages (core, mechanisms, http, extensions, mcp, legacy). The x402.org site has
# its dependencies installed but is not built. The declaration build of the largest packages does not fit in
# Node's default heap on a machine with 8 GB, so the limit is raised (for later rebuilds too), and turbo builds
# one package per 6 GB of memory at a time.
ENV NODE_OPTIONS=--max-old-space-size=4096
RUN cd typescript && pnpm install --frozen-lockfile --ignore-scripts
RUN cd typescript \
    && jobs="$(awk '/MemTotal/ { n = int($2 / 6291456); print (n < 1) ? 1 : n }' /proc/meminfo)" \
    && pnpm exec turbo run build --filter='./packages/**' --concurrency="$jobs"

# Go: the v2 module and the legacy v1 module.
RUN cd go && go mod download && go build ./... && go test -count=1 -run '^$' ./... > /dev/null
RUN cd go/legacy && go mod download

# Python
RUN cd python/x402 && uv python install && uv sync --all-extras --dev --frozen

# Java
RUN cd java && mvn -B -q -DskipTests package

# EVM contracts; this also fetches the solc release that foundry.toml pins.
RUN cd contracts/evm && forge build

# Smoke tests. A failure is logged and does not abort the build; they also fetch what only a test run needs
# (the Surefire provider for Maven). Vitest is called directly because the packages' `test` script also fails
# when coverage is under its threshold.
RUN cd typescript && (pnpm --filter @x402/core --filter @x402/evm exec vitest run \
      || echo "WARNING: TypeScript tests reported failures")
RUN cd go && (go test -count=1 ./... || echo "WARNING: Go tests reported failures")
RUN cd python/x402 && (uv run --frozen pytest -q || echo "WARNING: Python tests reported failures")
RUN cd java && (mvn -B -q -Pcoverage test || echo "WARNING: Java tests reported failures")
RUN cd contracts/evm && (forge test --no-match-contract ForkTest || echo "WARNING: forge tests reported failures")

# Everything is fetched: later commands must not wait on a network that is not there.
ENV GOPROXY=off \
    UV_OFFLINE=1 \
    FOUNDRY_OFFLINE=true
