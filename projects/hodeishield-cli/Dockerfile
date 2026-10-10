FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    CARGO_TERM_COLOR=never
# build-essential, cmake and pkg-config cover the C build steps of the TLS dependencies (aws-lc-sys). The keychain
# backend on Linux (zbus Secret Service) is pure Rust, so no libdbus or libsecret is needed.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential cmake pkg-config git \
    && rm -rf /var/lib/apt/lists/*

# Rust toolchain manager only; the toolchain itself is installed below from the checkout's rust-toolchain.toml.
# rustup-init is pinned to a release and verified against its published sha256 before it runs.
ARG RUSTUP_VERSION=1.29.1
ARG RUSTUP_INIT_SHA256=dda7234360b7f578ca8b0ddcb80145646fa61a67c1720a5abc7051b35c9fcb71
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/rustup-init \
      "https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/x86_64-unknown-linux-gnu/rustup-init" \
    && echo "${RUSTUP_INIT_SHA256}  /tmp/rustup-init" | sha256sum -c - \
    && chmod +x /tmp/rustup-init \
    && /tmp/rustup-init -y --no-modify-path --profile minimal --default-toolchain none \
    && rm /tmp/rustup-init

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install exactly the channel, profile and components pinned in /src/rust-toolchain.toml.
RUN rustup toolchain install && rustc --version && cargo --version

# Fetch every dependency (all targets of the workspace) into $CARGO_HOME now: the audit phase has no network.
RUN cargo fetch --locked

# Debug build (debug info on by default) of the whole workspace, including tests, examples and the xtask crate.
# The binary is /src/target/debug/hodeishield.
RUN cargo build --workspace --all-targets --locked

# Build the test binaries too (no-op when already built), so everything the tests need is compiled and cached.
RUN cargo test --workspace --no-run --locked

# Run the tests, but do not let a failing test abort the build. The suites use local mock HTTP servers (mockito) on
# 127.0.0.1 and need no external network.
RUN cargo test --workspace --locked || echo "WARNING: cargo test reported failures"

# The audit phase runs without network: make cargo refuse network access from here on.
ENV CARGO_NET_OFFLINE=true
