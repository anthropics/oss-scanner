FROM rust:1.96-trixie

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential cmake pkg-config libssl-dev libudev-dev protobuf-compiler python3 \
    && rm -rf /var/lib/apt/lists/*

# Anvil lets provider and signer tests run against a local node without network access.
RUN curl -sSfL https://foundry.paradigm.xyz | bash \
    && /root/.foundry/bin/foundryup --install stable
ENV PATH="/root/.foundry/bin:${PATH}"

# Keep the checkout and Cargo caches available to the offline scanner.
COPY . /src
WORKDIR /src
RUN cargo fetch --locked

# Retain symbols and frame pointers, and avoid LTO's build-time memory overhead.
ENV CARGO_NET_OFFLINE=true \
    CARGO_BUILD_JOBS=4 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    CARGO_PROFILE_RELEASE_STRIP=none \
    CARGO_PROFILE_RELEASE_LTO=false \
    RUSTFLAGS="-C force-frame-pointers=yes"

# Build every crate with all features, including transports and hardware/cloud signers.
RUN cargo build --locked --release --workspace --all-features

# Prebuild offline unit tests for encodings, consensus types, RPC types and local signing.
# Tests use the debug profile: alloy-signer-local's yubihsm dev-dependency refuses release builds.
RUN cargo test --locked --lib --all-features --no-run \
      -p alloy-consensus -p alloy-eips -p alloy-rpc-types-eth -p alloy-rpc-types-engine \
      -p alloy-json-rpc -p alloy-signer -p alloy-signer-local -p alloy-genesis
