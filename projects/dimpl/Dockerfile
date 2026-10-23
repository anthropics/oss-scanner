FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang libclang-dev cmake git libssl-dev \
      pkg-config autoconf automake libtool python3 \
    && rm -rf /var/lib/apt/lists/*

ARG CARGO_BUILD_JOBS=4
# Keep the existing fuzz targets usable after the audit loses network access.
RUN rustup toolchain install nightly --profile minimal --component rust-src \
    && cargo +nightly install cargo-fuzz --locked

# The scanner supplies the dimpl checkout as the build context.
COPY . /src
WORKDIR /src
RUN cargo fetch --locked \
    && cargo fetch --manifest-path fuzz/Cargo.toml

ENV CARGO_NET_OFFLINE=true \
    RUSTFLAGS="-C force-frame-pointers=yes"

# Include both crypto providers, certificate generation, and the provider-free API.
RUN cargo build --locked --all-targets --all-features \
    && cargo build --locked --no-default-features

# Tests include DTLS 1.2/1.3 and local OpenSSL/wolfSSL interoperability peers.
RUN cargo test --locked \
    && cargo test --locked --no-default-features --features aws-lc-rs \
    && cargo test --locked --no-default-features --features rust-crypto

# Precompile every harness, including its sanitizer runtime, for offline fuzzing.
RUN cargo +nightly fuzz build
