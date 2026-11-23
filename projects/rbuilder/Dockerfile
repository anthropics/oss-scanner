FROM rust:1.95-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates clang cmake git libclang-dev \
        libsqlite3-dev libssl-dev pkg-config protobuf-compiler libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

# Keep the image's toolchain active even though upstream tracks stable.
ENV RUSTUP_TOOLCHAIN=${RUST_VERSION} \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    CARGO_INCREMENTAL=0

WORKDIR /src
COPY . .
RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true \
    PATH="/src/target/release:${PATH}"

RUN cargo build --locked --release --package rbuilder --bin rbuilder
RUN cargo test --locked --release --lib --package rbuilder-primitives --no-run
