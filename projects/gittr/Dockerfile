# Build context is a fresh checkout of https://github.com/arbadacarbaYK/gittr
# (this Dockerfile lives in the OSS Scanner enrolment repo, not in that checkout).
# Network is available for this build and is removed afterwards.
FROM node:20-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/usr/local/go/bin:${PATH}" \
    GOPROXY=https://proxy.golang.org,direct \
    GOTOOLCHAIN=local \
    CGO_ENABLED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential python3 pkg-config \
    && rm -rf /var/lib/apt/lists/*

# go.mod says go 1.25.0. Fetch during the build so later offline work does not.
ARG GO_VERSION=1.25.0
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tgz \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm /tmp/go.tgz \
    && go version

# ui/yarn.lock is Yarn v1.
RUN corepack enable && corepack prepare yarn@1.22.22 --activate

COPY . /src
WORKDIR /src

# UI dependencies from the lockfile. Native addons (bufferutil, utf-8-validate) need the compilers above.
RUN cd /src/ui && yarn install --frozen-lockfile

# The unit-test script calls vitest, which is not in the lockfile. Install it now so tests can run offline.
RUN cd /src/ui && yarn add --dev vitest@3.2.4

# Git server that the public forge runs. These three commands are the bridge, the SSH server, and the CLI.
RUN cd /src/ui/gitnostr \
    && go build -o /usr/local/bin/git-nostr-bridge ./cmd/git-nostr-bridge \
    && go build -o /usr/local/bin/git-nostr-ssh ./cmd/git-nostr-ssh \
    && go build -o /usr/local/bin/git-nostr-cli ./cmd/git-nostr-cli

# A failing test must not throw the image away. The agent can re-run the same command with no network.
RUN cd /src/ui && (yarn test:unit || echo "WARNING: yarn test:unit reported failures")
