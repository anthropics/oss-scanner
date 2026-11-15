# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: 2026 ReallyMe Technologies Limited
# SPDX-License-Identifier: Apache-2.0

FROM rust:1.100.0-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV RUSTUP_TOOLCHAIN=1.100.0 \
    CARGO_BUILD_JOBS=4 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1 \
    CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C force-frame-pointers=yes" \
    CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C force-frame-pointers=yes"

RUN apt-get update \
    && apt-get install -y --no-install-recommends perl pkg-config python3 \
    && rm -rf /var/lib/apt/lists/* \
    && rustup component add clippy rustfmt \
    && rustup target add wasm32-unknown-unknown

WORKDIR /src
COPY . /src
RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true \
    OPENSSL_DIR=/opt/reallyme-openssl/install \
    OPENSSL_STATIC=1

# Build against the same locked OpenSSL source as Crypto CI. Keep its headers
# and libraries available for retesting, and discard build intermediates in
# the same layer so the image can be used on a small audit machine.
RUN --network=none <<'BUILD'
set -euo pipefail
export CARGO_TARGET_DIR=/tmp/reallyme-crypto-target
host="$(rustc -vV | sed -n 's/^host: //p')"
test -n "$host"
cargo build --locked -p optional-provider-build
MAKEFLAGS="-j${CARGO_BUILD_JOBS}" "$CARGO_TARGET_DIR/debug/optional-provider-build" \
    --target "$host" --out-dir /opt/reallyme-openssl

cargo fmt --all --check
cargo clippy --locked --workspace --all-targets --all-features -- -D warnings
cargo build --locked -p crypto-ffi
install -Dm755 "$CARGO_TARGET_DIR/debug/libcrypto_ffi.so" /opt/reallyme-crypto/lib/libcrypto_ffi.so
cargo build --locked -p reallyme-crypto-wasm --target wasm32-unknown-unknown
install -Dm644 "$CARGO_TARGET_DIR/wasm32-unknown-unknown/debug/reallyme_crypto_wasm.wasm" \
    /opt/reallyme-crypto/lib/reallyme_crypto_wasm.wasm

# Use Cargo's artifact metadata because test executable names and locations
# can vary with the compiler and selected features.
cargo test --locked -p crypto-conformance-vectors --all-features --test vectors_tests \
    --no-run --message-format=json > /tmp/reallyme-crypto-vectors.json
python3 - <<'PYTHON'
import json
import shutil
from pathlib import Path

executables = []
with Path('/tmp/reallyme-crypto-vectors.json').open(encoding='utf-8') as messages:
    for line in messages:
        artifact = json.loads(line)
        if (
            artifact.get('reason') == 'compiler-artifact'
            and artifact['target']['name'] == 'vectors_tests'
            and artifact['profile']['test']
            and artifact.get('executable')
        ):
            executables.append(Path(artifact['executable']))

if len(executables) != 1:
    raise SystemExit('Cargo did not identify exactly one vectors_tests executable.')

destination = Path('/opt/reallyme-crypto/bin/vectors_tests')
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(executables[0], destination)
PYTHON
rm -rf -- "$CARGO_TARGET_DIR" /opt/reallyme-openssl/build
rm -- /tmp/reallyme-crypto-vectors.json
BUILD

# Log a smoke test failure without withholding the image needed to diagnose it.
RUN --network=none /opt/reallyme-crypto/bin/vectors_tests \
      manifest_tests::shared_negative_vectors_pin_fail_closed_semantics --exact \
    || printf '%s\n' 'WARNING: the fail-closed conformance smoke test failed.' >&2
