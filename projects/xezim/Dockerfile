# xezim: a SystemVerilog simulator in Rust. The core parser/elaborator is a git
# dependency (aionhw/xezim-core) fetched by cargo during this online build.
FROM rust:1.92-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUSTFLAGS="-C force-frame-pointers=yes"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang pkg-config git python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch every dependency (crates and the xezim-core git dependency) while online.
RUN cargo fetch

# Release build with debug info (the release profile keeps debuginfo), plus a
# debug build, which keeps overflow checks and debug assertions on.
RUN cargo build --release --bin xezim && cargo build --bin xezim

# Build the test binaries so they can run offline; a failing test must not
# abort the image build.
RUN (cargo test --release --no-run || echo "WARNING: test build failed") \
 && (cargo test --release --test misc -- --test-threads=4 || echo "WARNING: misc tests reported failures")

# Drivers: target/release/xezim and target/debug/xezim; the regression corpus is
# tests/ (SystemVerilog sources embedded in Rust tests).
