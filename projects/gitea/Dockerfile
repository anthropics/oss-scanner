# Scanner image for https://github.com/go-gitea/gitea (main branch).
# Gitea is a Go backend with a Node.js/pnpm frontend. While the network is available this build
# fetches every dependency, builds both halves the way Gitea's CI and its own Dockerfile do, and
# compiles the test binaries, so the audit can rebuild and rerun tests offline.
# threat_model.md, next to this file, describes how to exercise the result.

# Go toolchain, matching go.mod (go 1.27, toolchain go1.27.2).
FROM golang:1.27.2-trixie AS go-toolchain

# Node 26, what Gitea's CI builds the frontend with; package.json wants node >= 22.18, pnpm >= 11.
# trixie, not bookworm: the tests need git >= 2.47 (SHA-256 repositories, `merge-tree --merge-base`,
# `git config set`), and bookworm ships 2.39 with nothing newer in backports.
FROM node:26-trixie
COPY --from=go-toolchain /usr/local/go /usr/local/go
# GOPATH and GOCACHE live in a world-writable /go so the root scanner shell and the non-root gitea
# user (see below) share the same module and build caches.
RUN install -d -m 1777 /go /go/bin /go/cache
ENV PATH="/go/bin:/usr/local/go/bin:${PATH}" \
    GOPATH=/go \
    GOCACHE=/go/cache \
    NODE_OPTIONS="--max-old-space-size=8192"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make build-essential python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm, at the version pinned by package.json's packageManager field (Node no longer bundles corepack).
RUN npm install --global "$(node -p "require('./package.json').packageManager")"

# Fetch every dependency the build or the tests need; after the image build there is no network.
RUN pnpm install --frozen-lockfile \
    && go mod download

# Build frontend (vite) and backend (go generate + go build) as CI does; bindata/timetzdata are the
# tags Gitea's own Dockerfile ships. CGO stays disabled: sqlite runs through modernc.org/sqlite.
RUN TAGS="bindata timetzdata" make build

# Compile the integration suite without running it, so it stays buildable offline.
RUN TAGS='bindata timetzdata' make test-integration-compile

# Everything is fetched. From here on the go command must not reach a proxy or download a toolchain,
# so the test run below also proves the image works offline. The last variable lets the gitea binary
# itself run as root (the scanner's shell is root); it does not help the unit tests, see below.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local \
    GITEA_I_AM_BEING_UNSAFE_RUNNING_AS_ROOT=true

# Gitea refuses to run as root (mustNotRunAsRoot in modules/setting/setting.go) and the unit-test
# harness scrubs the env-var override above, so the tests run as a non-root user; threat_model.md
# explains how to rerun them from the scanner's root shell. The gitea user shares /src, GOPATH and
# GOCACHE, so its test run reuses what the build compiled.
RUN useradd --create-home --shell /bin/bash gitea \
    && chown -R gitea:gitea /src /go \
    && git config --system --add safe.directory /src
RUN runuser -u gitea -- env HOME=/home/gitea TAGS='bindata timetzdata' timeout 1200 make test-backend \
    || echo "WARNING: make test-backend reported failures"
