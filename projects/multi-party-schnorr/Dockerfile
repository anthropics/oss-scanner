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

# Build the libraries with all features (must succeed).
RUN cargo build --workspace --all-features --locked \
    && cargo build --workspace --all-features --locked --release

# Pre-compile and run tests; failures are reported but do not fail the image.
RUN (cargo test --workspace --all-features --locked --release --no-run \
     && cargo test --workspace --all-features --locked --release) \
    || echo "WARNING: workspace tests failed to build or run"

ENV CARGO_NET_OFFLINE=true
