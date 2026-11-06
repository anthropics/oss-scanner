FROM rust:1.90.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=always \
    CARGO_INCREMENTAL=0 \
    RUST_BACKTRACE=1 \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config libssl-dev \
      build-essential clang cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src/bdk-ffi

RUN cargo fetch --locked
RUN cargo build --locked --all-targets
RUN cargo test --locked --no-run

RUN timeout 30m cargo test --locked -- --test-threads=1 \
    || echo "WARNING: tests reported failures; image remains usable offline"

WORKDIR /src
ENV CARGO_NET_OFFLINE=true
