FROM rust:1.95-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# The repository does not commit Cargo.lock; resolve it once here and fetch everything.
RUN cargo generate-lockfile && cargo fetch

# Build the workspace (lib, examples, dkls-metrics, msg-relay) in debug and release,
# matching CI (`cargo test --tests --all --release`).
RUN cargo build --workspace --all-targets --features sl-dkls23/test-support \
    && cargo test --workspace --tests --features sl-dkls23/test-support --no-run \
    && cargo test --workspace --tests --features sl-dkls23/test-support --release --no-run

RUN cargo test --workspace --tests --features sl-dkls23/test-support --release \
    || echo "WARNING: cargo test reported failures"

ENV CARGO_NET_OFFLINE=true
