# Scanner image for https://github.com/stratum-mining/stratum.
#
# The audit runs offline, so this build installs both toolchains the repository uses, fetches every crate, and
# compiles the workspace, its tests, its examples and its fuzz targets. threat_model.md, next to this file, says
# how to run each of them.

# The repository pins its toolchain in rust-toolchain.toml (1.75.0) and fuzz/rust-toolchain.toml (nightly); installing
# them needs the network, so both happen here.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# The image's gcc covers the only native builds (secp256k1-sys, libfuzzer-sys); python3 is for ad-hoc scripts.
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# The pinned toolchain plus the components rust-toolchain.toml asks for, and nightly with the llvm-tools that
# `cargo fuzz coverage` needs. cargo-fuzz itself is built from crates.io, since the image has no prebuilt binary for it.
RUN rustup toolchain install \
    && rustup toolchain install nightly --component rustfmt --component clippy --component llvm-tools-preview \
    && cargo +nightly install cargo-fuzz --locked

# Every crate the workspace and the fuzz crate depend on.
RUN cargo fetch && (cd fuzz && cargo fetch)

# The workspace and its tests with the default features, as CI tests them (--all-features would turn on channels-sv2's
# no_std feature, whose tests need std), then the examples CI runs, each with the features it needs. A step that fails fails the build, and primary_contact gets the log.
RUN cargo build --workspace && cargo test --workspace --no-run \
    && cargo build --manifest-path=sv1/Cargo.toml --example client_and_server \
    && cargo build --manifest-path=sv2/framing-sv2/Cargo.toml --example sv2_frame \
    && cargo build --manifest-path=sv2/codec-sv2/Cargo.toml --example unencrypted \
    && cargo build --manifest-path=sv2/codec-sv2/Cargo.toml --example encrypted --features=noise_sv2 \
    && cargo build --manifest-path=sv2/binary-sv2/Cargo.toml --example encode_decode \
    && cargo build --manifest-path=sv2/noise-sv2/Cargo.toml --example handshake \
    && cargo build --manifest-path=sv2/extensions-sv2/Cargo.toml --example extensions_negotiation \
    && cargo build --manifest-path=sv2/extensions-sv2/Cargo.toml --example worker_specific_hashrate_tracking

# The fuzz targets, with the sanitizer instrumentation cargo-fuzz adds, so `cargo fuzz run` works offline, and the
# shared seed corpus that the fuzz CI workflow checks out next to them (one directory per target).
RUN cd fuzz && cargo fuzz build \
    && git clone --depth 1 https://github.com/stratum-mining/stratum-fuzzing-corpus repo-corpus \
    && test -d repo-corpus/corpus/deserialize_sv2frame

# Run the tests so the log shows the image works, without letting a failure abort the build.
RUN (timeout 1200 cargo test --workspace || echo "WARNING: cargo test reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
