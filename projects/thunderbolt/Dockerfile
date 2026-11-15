# Thunderbolt: React/Vite app (src/, shared/), Bun backend, Bun CLI, Tauri shell (src-tauri/) and a Rust crate (crates/).
# Every tool version is read from the checkout (ci.yml, rust-toolchain.toml), so this file follows Thunderbolt's pins.
# Not prepared: the Playwright e2e stack (Postgres + PowerSync containers), which cannot run offline here.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
# The second line is Tauri's Linux build deps, as listed in ci.yml's `rust` job (which runs on Ubuntu 24.04).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip xz-utils build-essential pkg-config file \
      libwebkit2gtk-4.1-dev libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Node and Bun versions come from ci.yml. The backend job pins its own Bun (the frontend's hung inside PGlite there),
# so the `bun` wrapper runs that pin under /src/backend and the frontend pin everywhere else, as CI does.
# Everything goes in /usr/local/bin because Ubuntu's /etc/profile resets PATH in login shells.
RUN set -eu; ci=.github/workflows/ci.yml; \
    # pin <job> <key>: the key's value inside that one job, unquoted; the format checks below fail the build loudly
    pin() { awk -v job="  $1:" -v key="$2:" '$0 == job { f = 1; next } f && /^  [A-Za-z0-9_-]+:/ { exit } \
      f && $1 == key { gsub(/["\047]/, "", $2); print $2; exit }' "$ci"; }; \
    node_major="$(pin typescript node-version)"; node_major="${node_major%%.*}"; \
    frontend_bun="$(pin typescript bun-version)"; backend_bun="$(pin backend bun-version)"; \
    printf '%s\n' "$node_major" | grep -Eqx '[0-9]+'; \
    for v in "$frontend_bun" "$backend_bun"; do printf '%s\n' "$v" | grep -Eqx '[0-9]+(\.[0-9]+){2}'; done; \
    node_url="https://nodejs.org/dist/latest-v$node_major.x"; \
    node_arch="$(dpkg --print-architecture | sed 's/amd64/x64/')"; \
    node_tarball="$(curl -fsSL "$node_url/SHASUMS256.txt" | awk -v want="-linux-$node_arch.tar.xz" '$2 ~ want "$" { print $2 }')"; \
    curl -fsSL "$node_url/$node_tarball" | tar -xJ -C /usr/local --strip-components=1; \
    curl -fsSL https://bun.sh/install -o /tmp/bun-install.sh; \
    # HOME=/tmp keeps the installer from adding its own bin directory to /root/.bashrc, ahead of the wrapper
    HOME=/tmp BUN_INSTALL=/opt/bun-frontend bash /tmp/bun-install.sh "bun-v$frontend_bun"; \
    HOME=/tmp BUN_INSTALL=/opt/bun-backend bash /tmp/bun-install.sh "bun-v$backend_bun"; \
    rm /tmp/bun-install.sh; \
    printf '%s\n' '#!/bin/bash' \
      'case "$PWD/" in /src/backend/*) bun=/opt/bun-backend/bin/bun ;; *) bun=/opt/bun-frontend/bin/bun ;; esac' \
      'exec -a "${0##*/}" "$bun" "$@"' > /usr/local/bin/bun; \
    chmod +x /usr/local/bin/bun; ln -s bun /usr/local/bin/bunx; \
    node --version; bun --version; (cd backend && bun --version)

# rustup installs each tree's own toolchain from its rust-toolchain.toml (src-tauri: stable, crates: a pinned release).
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none --no-modify-path \
    && ln -s /root/.cargo/bin/* /usr/local/bin/ \
    && (cd src-tauri && rustup toolchain install) \
    && (cd crates/thunderbolt-acp-client && rustup toolchain install)

# One frozen install per workspace: each has its own bun.lock (shared/agent-core uses the root's).
RUN bun install --frozen-lockfile \
    && (cd backend && bun install --frozen-lockfile) \
    && (cd cli && bun install --frozen-lockfile) \
    && (cd miniapps && bun install --frozen-lockfile) \
    && (cd web && bun install --frozen-lockfile)

# The browsers CI installs for the agent-core browser check, so sandbox and CSP findings can be shown in a real engine.
RUN bunx playwright install --with-deps chromium webkit && rm -rf /var/lib/apt/lists/*

# The frontend build, as CI runs it (vite runs under Node; Tauri's frontendDist is ../dist).
RUN NODE_ENV=production NODE_OPTIONS=--max-old-space-size=4096 bun run build

# src-tauri/.cargo/config.toml asks for target-cpu=native on x86-64 Linux; build for a generic CPU instead, so the
# binaries still run if the scan machine's CPU differs from the build machine's. ENV, so later cargo runs reuse them.
ENV CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C target-cpu=x86-64"
# Build every target, as CI does, so `cargo test --offline` only has to run.
RUN (cd src-tauri && cargo build --all-targets) \
    && (cd crates/thunderbolt-acp-client && cargo build --all-targets)
