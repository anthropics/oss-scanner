FROM rust:1.97.1-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    CARGO_NET_RETRY=10 \
    CARGO_INCREMENTAL=0 \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates clang cmake curl git jq libclang-dev \
      make nasm pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path tooling/event-monitor/Cargo.toml

RUN make leanSpec/fixtures

RUN cargo build --locked --profile release-fast --bin ethlambda \
    && cargo test --locked --profile release-fast --workspace --no-run \
    && cargo test --locked --profile release-fast -p ethlambda-types --lib \
        --features preset-minimal --no-run \
    && cargo test --locked --profile release-fast -p ethlambda-state-transition --lib \
        --features preset-minimal --no-run \
    && cargo test --locked --manifest-path tooling/event-monitor/Cargo.toml --no-run

ENV CARGO_NET_OFFLINE=true
