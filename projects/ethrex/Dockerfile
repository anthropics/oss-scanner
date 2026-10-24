FROM rust:1.93.0-slim-bookworm AS base

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    CARGO_NET_RETRY=10 \
    CARGO_INCREMENTAL=0 \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1 \
    VERGEN_GIT_BRANCH=unknown \
    VERGEN_GIT_SHA=unknown \
    VERGEN_IDEMPOTENT=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates clang cmake curl git libclang-dev \
      libssl-dev pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN arch="${TARGETARCH:-$(uname -m)}" \
    && case "$arch" in \
        arm64|aarch64) asset=solc-static-linux-arm ;; \
        amd64|x86_64) asset=solc-static-linux ;; \
        *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac \
    && curl -fsSL --retry 5 --retry-all-errors --retry-connrefused --connect-timeout 30 \
        -o /usr/local/bin/solc "https://github.com/ethereum/solidity/releases/download/v0.8.31/$asset" \
    && chmod +x /usr/local/bin/solc \
    && solc --version

COPY . /src
WORKDIR /src

ENV COMPILE_CONTRACTS=true

RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path tooling/Cargo.toml

RUN make -C tooling/ef_tests/blockchain download-test-vectors

FROM base AS release-build
RUN cargo build --locked --profile release --bin ethrex --features l2,l2-sql

FROM base AS test-build
RUN cargo test --locked --profile release-fast --workspace --features rocksdb \
        --exclude 'ethrex-l2*' --exclude ethrex-prover --exclude ethrex-guest-program --no-run \
    && cargo test --locked --profile release-fast -p ethrex-l2 --lib --no-run \
    && cargo test --locked --profile release-fast -p ethrex-guest-program --no-default-features --no-run \
    && cargo test --locked --profile release-fast --manifest-path tooling/Cargo.toml \
        -p ef_tests-blockchain --no-run \
    && cargo test --locked --profile release-fast --manifest-path tooling/Cargo.toml \
        -p ef_tests-blockchain --features stateless --no-run

FROM test-build AS final
COPY --from=release-build /src/target/release /src/target/release
ENV CARGO_NET_OFFLINE=true
