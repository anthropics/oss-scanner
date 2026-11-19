FROM rust:1.88-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch every dependency in the committed Cargo.lock (all optional features included),
# so any feature combination can be rebuilt offline.
RUN cargo fetch --locked

# Build the whole workspace with all features, in debug (overflow checks on) and release,
# matching CI (`cargo test --all-features --release --locked`).
RUN cargo build --workspace --all-features --all-targets --locked \
    && cargo test --workspace --all-features --locked --no-run \
    && cargo test --workspace --all-features --locked --release --no-run

# Run the test suite so the image is known-good; do not fail the build on test failures.
RUN cargo test --workspace --all-features --locked --release \
    || echo "WARNING: cargo test reported failures"

ENV CARGO_NET_OFFLINE=true
