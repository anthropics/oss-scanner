# The scanner supplies a HarfRust checkout as the build context. Fetch all
# toolchains, crates and font corpora before the audit loses network access.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer" \
    CARGO_PROFILE_RELEASE_DEBUG=2 \
    CARGO_PROFILE_RELEASE_STRIP=false \
    CARGO_PROFILE_RELEASE_LTO=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake curl git llvm pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# cargo-fuzz needs nightly; keep both toolchains and Rust sources for offline work.
RUN rustup toolchain install nightly --profile minimal --component rust-src \
    && cargo install --locked cargo-fuzz

COPY . /src
WORKDIR /src

# HarfRust does not commit Cargo.lock. Resolve it once during setup and retain
# the lockfile, registry cache and git dependencies (including the test oracle).
RUN cargo generate-lockfile && cargo fetch --locked

# Use the same external font sources as OSS-Fuzz. Keep only font files, outside
# /src, so the audit remains focused on HarfRust. Preserve duplicate basenames.
RUN mkdir -p /opt/font-corpus /tmp/font-src \
    && git clone --depth 1 https://github.com/unicode-org/text-rendering-tests.git /tmp/font-src/text-rendering-tests \
    && git clone --depth 1 https://github.com/googlefonts/color-fonts.git /tmp/font-src/color-fonts \
    && git clone --depth 1 https://github.com/harfbuzz/harfbuzz.git /tmp/font-src/harfbuzz \
    && find /tmp/font-src/text-rendering-tests/fonts /tmp/font-src/color-fonts/fonts /tmp/font-src/harfbuzz/test \
         -type f \( -iname '*.ttf' -o -iname '*.otf' -o -iname '*.ttc' -o -iname '*.otc' \) \
         -exec cp --backup=numbered -t /opt/font-corpus {} + \
    && rm -rf /tmp/font-src \
    && test -n "$(ls -A /opt/font-corpus)"

ENV CARGO_NET_OFFLINE=true

# Include optional ICU/tracing and C API subset/draw/paint features. Preserve a
# release build to distinguish production behavior from debug-only panics.
RUN cargo build --locked --workspace --all-features \
    && cargo build --locked --release --workspace --all-features \
    && cargo test --locked --workspace --all-features --no-run \
    && cargo build --locked -p harfrust --no-default-features --features libm,tracing --target-dir target/no-std

# Match OSS-Fuzz's optimized AddressSanitizer build with debug assertions. The
# fuzzer is target/x86_64-unknown-linux-gnu/release/fuzz_shape on the scanner.
RUN cargo +nightly fuzz build -O --debug-assertions

# Small C consumers of the shared library, useful for exercising the FFI boundary.
RUN cc -g -fno-omit-frame-pointer -Iharfrust_capi/include \
      harfrust_capi/examples/shape.c -Ltarget/debug -lharfrust_c \
      -Wl,-rpath,/src/target/debug -o target/debug/hr-shape-c \
    && cc -g -fno-omit-frame-pointer -Iharfrust_capi/include \
      harfrust_capi/examples/subset.c -Ltarget/debug -lharfrust_c \
      -Wl,-rpath,/src/target/debug -o target/debug/hr-subset-c \
    && cc -g -fno-omit-frame-pointer -Iharfrust_capi/include \
      harfrust_capi/examples/rendering.c -Ltarget/debug -lharfrust_c \
      -Wl,-rpath,/src/target/debug -o target/debug/hr-rendering-c

# Keep the environment usable for auditing even if an upstream test fails.
RUN cargo test --locked --workspace --all-features \
    || echo "WARNING: HarfRust tests reported failures"
