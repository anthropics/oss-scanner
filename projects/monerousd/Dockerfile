# MoneroUSD: the node (Rust workspace in monerousd-node-zkdag/, with its vendored prover under vendor/) and the wallet core
# (monerousd-wallet-v2/src-tauri). Built as its maintainers build it; every crate is fetched here so tests can run offline.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential clang cmake pkg-config git python3 libssl-dev liblzma-dev \
      libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev libayatana-appindicator3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
COPY . /src
WORKDIR /src
# every dependency of both workspaces, so the audit (offline) can build and test
RUN cd monerousd-node-zkdag && cargo fetch && cd ../monerousd-wallet-v2/src-tauri && cargo fetch
# the node, with debug info; the tests compiled (not run here: the node suite is long)
RUN cd monerousd-node-zkdag && CARGO_PROFILE_RELEASE_DEBUG=true cargo build --release --bin usdmd-node \
    && (cargo test --release --lib --no-run || echo "WARNING: the node's tests did not compile")
# the wallet's Rust core and its command-line harness (the Tauri app shell needs a display and is not built)
RUN cd monerousd-wallet-v2/src-tauri && (cargo build --release --bin wallet-harness || echo "WARNING: wallet-harness did not build")
