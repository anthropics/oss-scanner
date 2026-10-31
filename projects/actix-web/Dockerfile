FROM rust:1-trixie

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake git libssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

ARG CARGO_BUILD_JOBS=4

ENV CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS} \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true

RUN cargo build --locked --workspace --all-targets --all-features

RUN cargo test --locked --workspace --all-features
