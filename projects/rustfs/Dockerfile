FROM rust:1.99-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates clang cmake git libclang-dev libssl-dev lld \
      pkg-config protobuf-compiler python3 unzip \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Keep Cargo's registry, git sources and build artifacts in the image for offline audits.
# The checked-in protobuf/FlatBuffers sources do not require regeneration to build.
ENV CARGO_INCREMENTAL=0 \
    CARGO_BUILD_JOBS=4 \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    RUSTFLAGS="-C force-frame-pointers=yes -C link-arg=-fuse-ld=lld"

RUN curl --fail --location --retry 3 \
      https://dl.rustfs.com/artifacts/console/rustfs-console-latest.zip \
      --output /tmp/rustfs-console.zip \
    && unzip -q /tmp/rustfs-console.zip -d /src/rustfs/static \
    && rm /tmp/rustfs-console.zip \
    && cargo fetch --locked

ENV CARGO_NET_OFFLINE=true

# Build the server with its default features and line-table debug information.
RUN cargo build --frozen -p rustfs --bin rustfs \
    && cargo test --frozen -p rustfs-credentials -p rustfs-policy -p rustfs-signer --lib

CMD ["bash"]
