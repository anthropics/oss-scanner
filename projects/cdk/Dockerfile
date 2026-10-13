FROM rust:1.99.0-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    clang libclang-dev cmake ninja-build pkg-config protobuf-compiler \
    libssl-dev libsqlite3-dev python3 git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Keep source, dependencies, and debug artifacts available to the offline scanner.
COPY . /src
WORKDIR /src
# Install only the native toolchain; rust-toolchain.toml also lists mobile targets.
ENV RUSTUP_TOOLCHAIN=1.99.0 \
    CARGO_BUILD_JOBS=4 \
    RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo fetch --locked
RUN cargo build --locked -p cdk-mintd -p cdk-cli
RUN cargo test --locked --no-run --lib -p cashu -p cdk-common -p cdk -p cdk-sqlite -p cdk-axum
RUN cargo test --locked --offline --lib -p cashu -p cdk-common -p cdk -p cdk-sqlite -p cdk-axum \
    || echo "WARNING: library tests reported failures; inspect and rerun during the scan"
