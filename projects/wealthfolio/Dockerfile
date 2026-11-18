# OSS Scanner build for Wealthfolio (https://github.com/wealthfolio/wealthfolio), built with a checkout of that
# repository as the context. It builds and test-compiles the Rust workspace (core crates, Axum web server, Tauri
# desktop app) and the React frontend online, so tests, the server and browser tests run offline.
# Toolchain versions come from the checkout (rust-toolchain.toml, packageManager in package.json); only the Node
# major version (.node-version) is pinned here.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive
# Tauri's Linux system libraries (as in .github/workflows/pr-check.yml), plus tools for driving the web server by hand.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential pkg-config perl python3 \
      libgtk-3-dev libwebkit2gtk-4.1-dev librsvg2-dev libayatana-appindicator3-dev libxdo-dev \
      argon2 jq sqlite3 \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain none --no-modify-path

COPY . /src
WORKDIR /src

# Installs the channel and components named in rust-toolchain.toml.
RUN rustup toolchain install && rustc --version

ENV CI=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
# pnpm at the version in package.json's packageManager; web bundle in /src/dist (the server serves it and the Tauri
# build embeds it); Chromium and WebKit for the addon sandbox browser tests (WebKit is the desktop webview's engine).
RUN corepack enable \
    && pnpm install --frozen-lockfile \
    && pnpm build:types \
    && pnpm build \
    && pnpm exec playwright install --with-deps chromium webkit

# CONNECT_API_URL is needed by the storage-sqlite outbox tests (as in CI). Frame pointers help debuggers.
# No incremental cache: it would add about 8 GB to the image.
ENV CONNECT_API_URL=http://test.local \
    CARGO_INCREMENTAL=0 \
    RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo fetch --locked
ENV CARGO_NET_OFFLINE=true
# The server and app build scripts watch ../../.env (gitignored). While it is missing, Cargo reruns them on every
# command and relinks both packages. An empty file means no Connect configuration, the same as no file.
RUN touch .env

# The server binary (target/debug/wealthfolio-server) and every workspace test binary, including the AI tools'
# fixture-backed tests that CI runs separately. tauri::generate_context! writes an asset into OUT_DIR after Cargo's
# reference time, so the first test build leaves wealthfolio-app stale; the second pass settles it, and offline
# `cargo test --workspace` then starts without recompiling.
RUN cargo build --locked -p wealthfolio-server \
    && cargo test --locked --workspace --no-run \
    && cargo test --locked -p wealthfolio-ai --features test-utils --no-run \
    && cargo test --locked --workspace --no-run

CMD ["bash"]
