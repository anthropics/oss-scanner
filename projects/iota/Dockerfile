FROM rust:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1 \
    RUSTFLAGS="-C force-frame-pointers=yes -C force-unwind-tables=yes -C link-arg=-fuse-ld=lld"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates clang cmake git libpq-dev libudev-dev lld \
      pkg-config protobuf-compiler python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Install the toolchain pinned by the checkout while networking is available.
RUN rustup show active-toolchain

# Retain dependencies for both Rust workspaces, including their test targets.
RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path external-crates/move/Cargo.toml

RUN cargo build --locked --bin iota-node --bin iota-tool
RUN cargo test --locked -p iota-types --lib --no-run

ENV CARGO_NET_OFFLINE=true
