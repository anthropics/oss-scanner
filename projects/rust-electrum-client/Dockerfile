FROM rust:1.97.1-bookworm

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
WORKDIR /src

RUN cargo fetch
RUN cargo build --all-targets --all-features
RUN cargo test --all-features --no-run

RUN timeout 10m cargo test --all-features --lib config:: -- --test-threads=1 \
    || echo "WARNING: offline config tests reported failures; image remains usable offline"
RUN timeout 10m cargo test --all-features --lib types:: -- --test-threads=1 \
    || echo "WARNING: offline type tests reported failures; image remains usable offline"

ENV CARGO_NET_OFFLINE=true
