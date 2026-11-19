FROM rust:1.96.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=always \
    CARGO_INCREMENTAL=0 \
    RUST_BACKTRACE=1 \
    RUSTFLAGS="-C force-frame-pointers=yes --cfg bdk_wallet_unstable" \
    RUSTDOCFLAGS="--cfg bdk_wallet_unstable"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config libssl-dev \
      build-essential clang cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN cargo fetch
RUN cargo build --all-targets --all-features
RUN cargo test --all-features --no-run

RUN timeout 30m cargo test --all-features -- --test-threads=1 \
    || echo "WARNING: tests reported failures; image remains usable offline"

ENV CARGO_NET_OFFLINE=true
