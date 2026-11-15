# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: 2026 ReallyMe Technologies Limited
# SPDX-License-Identifier: Apache-2.0

FROM rust:1.100.0-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV RUSTUP_TOOLCHAIN=1.100.0 \
    CARGO_BUILD_JOBS=2 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1

# Use the repository's compiler and install the components needed on Linux.
RUN rustup component add clippy rustfmt \
    && rustup target add wasm32-unknown-unknown

WORKDIR /src
COPY . /src

# The scanner runs without network access after initial setup.
RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path probes/der-feature-unification/Cargo.toml \
    && cargo fetch --locked --manifest-path probes/jcs-feature-unification/Cargo.toml
ENV CARGO_NET_OFFLINE=true

# Keep the compiled Linux and WebAssembly boundaries available for inspection.
# Discard intermediate objects in the same layer to keep the image smaller.
RUN --network=none <<'BUILD'
set -euo pipefail
export CARGO_TARGET_DIR=/tmp/reallyme-codec-target

cargo build --locked -p reallyme-codec-ffi
install -Dm755 "$CARGO_TARGET_DIR/debug/libreallyme_codec_ffi.so" \
    /opt/reallyme-codec/lib/libreallyme_codec_ffi.so
cargo build --locked -p reallyme-codec-wasm --target wasm32-unknown-unknown
install -Dm644 "$CARGO_TARGET_DIR/wasm32-unknown-unknown/debug/reallyme_codec_wasm.wasm" \
    /opt/reallyme-codec/lib/reallyme_codec_wasm.wasm

rm -rf -- "$CARGO_TARGET_DIR"
BUILD
