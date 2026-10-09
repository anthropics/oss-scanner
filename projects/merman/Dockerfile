FROM rust:1.95.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_BUILD_JOBS=2 \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    MERMAN_SCAN_FEATURES="merman/analysis,merman/editor,merman/ascii,merman/png,merman/jpeg,merman/pdf,merman-ffi/all-diagrams,merman-ffi/analysis,merman-ffi/ascii,merman-ffi/svg,merman-ffi/png,merman-ffi/jpeg,merman-ffi/pdf,merman-ffi/layout-cytoscape,merman-ffi/layout-elk,merman-ffi/math,merman-ffi/native-runtime"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates build-essential clang pkg-config git python3 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN rustup component add rustfmt clippy \
    && cargo install cargo-nextest --version 0.9.103 --locked

COPY . /src
WORKDIR /src

# Fetch while online; the scanner must be able to rebuild and test offline.
RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path fuzz/Cargo.toml

RUN cargo build --offline --locked \
    -p merman -p merman-ffi -p merman-cli -p merman-lsp -p tree-sitter-mermaid \
    --features "$MERMAN_SCAN_FEATURES"

RUN cargo nextest run --offline --locked --no-run \
    -p merman -p merman-core -p merman-render -p merman-export \
    -p merman-ffi -p tree-sitter-mermaid \
    --features "$MERMAN_SCAN_FEATURES"

RUN cargo nextest run --offline --locked \
    -p merman -p merman-core -p merman-render -p merman-export \
    -p merman-ffi -p tree-sitter-mermaid \
    --features "$MERMAN_SCAN_FEATURES" \
    -E 'test(security) | test(sanitiz) | test(resource) | test(icon_registry) | package(tree-sitter-mermaid)'
