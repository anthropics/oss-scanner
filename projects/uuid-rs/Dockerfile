# Scanner image for https://github.com/uuid-rs/uuid.
#
# The audit runs offline, so this build installs the toolchains the repository's CI uses, fetches every crate for the
# workspace and the fuzz crate, and compiles the library with all features and its tests. threat_model.md, next to this
# file, says how to run each of them.

# Stable Rust, which is what CI tests with. clang and llvm are for AFL++ (cargo-afl), which CI uses as a fuzz canary.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends clang llvm llvm-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# The nightly that CI pins for Miri, with Miri's sysroot built now so it works without network later. Miri is the tool
# for checking the crate's `unsafe` code.
ARG MIRI_TOOLCHAIN=nightly-2026-08-25
RUN rustup toolchain install ${MIRI_TOOLCHAIN} --component miri --component rust-src \
    && cargo +${MIRI_TOOLCHAIN} miri setup \
    && cargo +${MIRI_TOOLCHAIN} miri setup --target s390x-unknown-linux-gnu
ENV MIRI_TOOLCHAIN=${MIRI_TOOLCHAIN}

# cargo-hack drives the per-feature test matrix that CI runs; cargo-afl builds and runs the fuzz targets under fuzz/.
RUN rustup component add clippy \
    && cargo install cargo-hack --locked \
    && (cargo install cargo-afl --locked && cargo afl config --build --force \
        || echo "WARNING: cargo-afl is not available; fuzz targets can still be run as tests")

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every crate the workspace (uuid, rng, examples, tests/smoke-test, tests/wasm32-getrandom-test) and the separate fuzz
# crate depend on, for stable and for the Miri nightly.
RUN cargo fetch \
    && cargo +${MIRI_TOOLCHAIN} fetch \
    && cargo fetch --manifest-path fuzz/Cargo.toml

# The library with every feature, its unit, doc and example tests, and the fuzz crate's regression tests. A step that
# fails fails the build, and primary_contact gets the log.
RUN cargo build --all-features \
    && cargo test --all-features --no-run \
    && cargo test --manifest-path fuzz/Cargo.toml --no-run

# Run the tests so the log shows the image works, without letting a failure abort the build.
RUN (timeout 1200 cargo test --all-features || echo "WARNING: cargo test reported failures") \
    && (timeout 600 cargo test --manifest-path fuzz/Cargo.toml || echo "WARNING: fuzz regression tests reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
