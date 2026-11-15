# The scanner supplies a rust-bitcoin checkout as the build context. All
# toolchains, crates and fuzz corpora must be fetched here, before the audit
# loses network access.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer" \
    CARGO_PROFILE_RELEASE_DEBUG=2 \
    CARGO_PROFILE_RELEASE_STRIP=false \
    CARGO_PROFILE_RELEASE_LTO=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang git pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# The fuzz targets are libFuzzer targets; keep nightly and Rust sources for
# offline cargo-fuzz work.
RUN rustup toolchain install nightly --profile minimal --component rust-src \
    && cargo install --locked cargo-fuzz

COPY . /src
WORKDIR /src

# rust-bitcoin does not commit Cargo.lock. Resolve it once during setup and
# retain the lockfile, registry cache and git dependencies.
RUN cargo generate-lockfile && cargo fetch --locked

# Seed the per-target fuzz corpora from the project's qa-assets repository
# (this is what the project's own CI fuzzing uses). Keep it outside /src so
# the audit remains focused on rust-bitcoin; fuzz/corpora.sh expects the QA
# checkout as its first argument.
RUN git clone --depth 1 https://github.com/rust-bitcoin/qa-assets.git /opt/qa-assets \
    && mkdir -p /opt/corpora \
    && (cd fuzz && cargo fuzz list) > /tmp/fuzz-targets \
    && while read -r t; do \
         ./fuzz/corpora.sh seed /opt/qa-assets "$t" \
         && mv "fuzz/corpus/$t" "/opt/corpora/$t"; \
       done < /tmp/fuzz-targets \
    && test -n "$(ls -A /opt/corpora)" \
    && rm -rf fuzz/corpus

ENV CARGO_NET_OFFLINE=true

# Build the workspace as its maintainers build it, debug and release, plus the
# no-default-features (no_std) configurations, and pre-compile the test
# binaries so the auditor can run them offline.
RUN cargo build --locked --workspace --all-features \
    && cargo build --locked --release --workspace --all-features \
    && cargo test --locked --workspace --all-features --no-run \
    && cargo build --locked --workspace --no-default-features

# Build every libFuzzer target (see fuzz/README.md). The optimized build with
# debug assertions is what the project's CI fuzzes with.
RUN cargo +nightly fuzz build \
    && cargo +nightly fuzz build -O --debug-assertions

# Keep the environment usable for auditing even if an upstream test fails.
RUN cargo test --locked --workspace --all-features \
    || echo "WARNING: rust-bitcoin tests reported failures"
