FROM rust:1.96-trixie

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential cmake pkg-config m4 libclang-dev libssl-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# Use the same LLVM installation as Reth's release Dockerfile, including JIT support.
COPY .github/scripts/install_llvm_ubuntu.sh /tmp/install_llvm.sh
RUN bash /tmp/install_llvm.sh && rm /tmp/install_llvm.sh \
    && rm -rf /var/lib/apt/lists/*

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
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g1 -fno-omit-frame-pointer" \
    CXXFLAGS="-g1 -fno-omit-frame-pointer"

# Preserve the node's default features, including JIT, JavaScript tracing and jemalloc.
RUN cargo build --locked --release --bin reth

# Prebuild offline unit tests for protocol decoding, trie integrity and block validation.
RUN cargo test --locked --release --lib --no-run \
      -p reth-eth-wire -p reth-ecies -p reth-trie-common -p reth-ethereum-consensus

ENV PATH="/src/target/release:${PATH}"
