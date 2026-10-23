FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_INCREMENTAL=0 \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates clang cmake curl git pkg-config python3 \
    && rm -rf /var/lib/apt/lists/* \
    && rustup component add clippy rustfmt \
    && rustup toolchain install nightly --profile minimal --component rust-src \
    && rustup target add thumbv7m-none-eabi riscv64imac-unknown-none-elf \
    && cargo install cargo-fuzz --locked

COPY . /src
WORKDIR /src

RUN cargo fetch \
    && cargo fetch --manifest-path fuzz/Cargo.toml

RUN ./spec-tests/download-vectors.sh

RUN cargo build --workspace --all-targets --exclude spec-tests \
    && cargo test --workspace --exclude spec-tests --no-run \
    && cargo test --workspace --exclude spec-tests --no-default-features --features alloc --no-run \
    && cargo test -p spec-tests --no-run \
    && cargo check -p libssz -p libssz-types -p libssz-merkle \
        --target thumbv7m-none-eabi --no-default-features --features alloc \
    && cargo check -p libssz -p libssz-types -p libssz-merkle \
        --target riscv64imac-unknown-none-elf --no-default-features --features alloc

RUN cd fuzz && cargo +nightly fuzz build

ENV CARGO_NET_OFFLINE=true
