FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang libclang-dev cmake pkg-config zstd python3 \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies a non-recursive checkout as the build context.
COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive

# These crates have separate manifests rather than a Cargo workspace.
RUN cargo fetch \
    && cargo fetch --manifest-path zstd-safe/Cargo.toml \
    && cargo fetch --manifest-path zstd-safe/zstd-sys/Cargo.toml

ENV CARGO_NET_OFFLINE=true \
    CFLAGS="-g -fno-omit-frame-pointer" \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN cargo test \
    && cargo test --features experimental,zstdmt,with-rust-allocator \
    && cargo test --manifest-path zstd-safe/Cargo.toml --features std,seekable \
    && cargo test --manifest-path zstd-safe/Cargo.toml --features std,seekable,with-rust-allocator \
    && cargo test --manifest-path zstd-safe/zstd-sys/Cargo.toml --features bindgen,experimental,seekable,zstdmt
