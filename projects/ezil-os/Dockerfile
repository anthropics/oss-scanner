# EZiL-OS: deterministic build for the OSS Scanner. The checkout lives at /src.
# Pins: base image by digest, Bun 1.3.14 and Node 22.16.0 (the versions .github/workflows/ci.yml uses), each
# release archive checked against its published sha256. Only dependency installs use the network; they run from
# the committed lockfiles with --frozen-lockfile, and Bun runs no dependency lifecycle scripts (no
# trustedDependencies are set). Not built: macos-electron (its postinstall downloads Electron), infra/, docker/.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip xz-utils python3 build-essential bash \
    && rm -rf /var/lib/apt/lists/*

ARG BUN_VERSION=1.3.14
ARG NODE_VERSION=22.16.0
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
      amd64) bun_arch=x64;     bun_sha=951ee2aee855f08595aeec6225226a298d3fea83a3dcd6465c09cbccdf7e848f; \
             node_arch=x64;    node_sha=f4cb75bb036f0d0eddf6b79d9596df1aaab9ddccd6a20bf489be5abe9467e84e ;; \
      arm64) bun_arch=aarch64; bun_sha=a27ffb63a8310375836e0d6f668ae17fa8d8d18b88c37c821c65331973a19a3b; \
             node_arch=arm64;  node_sha=eab80cb88f8fda1e65f5e8d0420c9809bdb320b03fd34976ab7161b6e703b910 ;; \
      *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/bun.zip "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-${bun_arch}.zip"; \
    echo "${bun_sha}  /tmp/bun.zip" | sha256sum -c -; \
    unzip -q /tmp/bun.zip -d /tmp/bun; \
    install -m 0755 "/tmp/bun/bun-linux-${bun_arch}/bun" /usr/local/bin/bun; \
    curl -fsSL -o /tmp/node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    echo "${node_sha}  /tmp/node.tar.xz" | sha256sum -c -; \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 --no-same-owner; \
    rm -rf /tmp/bun /tmp/bun.zip /tmp/node.tar.xz; \
    bun --version; node --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install every component the maintainers' CI tests, from the committed lockfiles. A failed install fails the build.
# tools/ has no dependencies and no lockfile by design, so it is tested without an install.
RUN set -eu; for d in app worker sdk mcp local native shell extensions/ezil-models; do \
      echo "== bun install: $d"; (cd "/src/$d" && bun install --frozen-lockfile); \
    done

# Unit tests, as CI runs them (no cloud credentials, no database, no Docker socket). Each package is time-bounded and
# a failure only warns, so the image is always produced. Tests that need a Docker socket or hosted services are
# expected to fail here; worker/src/*.container.test.ts are of that kind.
RUN for d in worker sdk mcp local native tools extensions/ezil-models; do \
      echo "== bun test: $d"; (cd "/src/$d" && timeout 300 bun test) || echo "WARNING: bun test failed or timed out in $d"; \
    done; \
    echo "== vitest: app"; (cd /src/app && timeout 300 bun run test) || echo "WARNING: app tests failed or timed out"
