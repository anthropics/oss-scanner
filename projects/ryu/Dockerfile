# Builds the open-source Ryu node: ryu-core (Apache-2.0, apps/core) and ryu-gateway (AGPL-3.0,
# apps/gateway). The scanner builds this with the amajorai/ryu checkout as the build context.
#
# Trixie, not bookworm, matching the repository's root Dockerfile (its release build needs glibc
# 2.38+). This image builds Core with the sandbox-wasmtime feature only.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang cmake pkg-config protobuf-compiler \
      libssl-dev libdbus-1-dev ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# There is no root Cargo workspace: Core and Gateway are separate manifests sharing one target dir.
# Debug builds keep full debug info; frame pointers make backtraces usable. Incremental state is
# off to save memory and disk. Everything is set here, before the first build, so later steps
# reuse the same artifacts. Tests use an isolated data dir and never touch an OS keychain.
ENV CARGO_TARGET_DIR=/src/target \
    CARGO_INCREMENTAL=0 \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    RYU_PROFILE=dev \
    RYU_KEYCHAIN=off \
    RYU_DIR=/tmp/ryu-scan

# Fetch every crate (including dev-dependencies) while the network is still available.
RUN cargo fetch --locked --manifest-path apps/gateway/Cargo.toml \
 && cargo fetch --locked --manifest-path apps/core/Cargo.toml
ENV CARGO_NET_OFFLINE=true

# The shipped binaries. They are copied out because the test builds below re-link
# target/debug/ with dev-dependency features enabled.
RUN cargo build --locked --manifest-path apps/gateway/Cargo.toml \
 && cargo build --locked --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime \
 && cp target/debug/ryu-gateway target/debug/ryu-core /usr/local/bin/

# Compile the test binaries now so they can run offline during the audit. ryu-core is one very
# large bin crate, so its test harness is built alone with two jobs to bound peak memory.
RUN cargo test --locked --no-run --manifest-path apps/gateway/Cargo.toml \
 && cargo test --locked --no-run --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime \
      --bin ryu-core --jobs 2

# Some async tests overflow the default 2 MiB test-thread stack in debug builds, and one overflow
# aborts the whole ryu-core test binary. Read at run time only, so nothing recompiles.
ENV RUST_MIN_STACK=8388608

# Run the cheap tests so we know the image works, with a time bound, and never fail the build.
RUN (timeout -k 30 240 cargo test --locked --manifest-path apps/gateway/Cargo.toml --no-fail-fast \
      -- --test-threads=4 || echo "WARNING: gateway tests reported failures or timed out") \
 && (timeout -k 30 300 cargo test --locked --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime \
      --bin ryu-core --no-fail-fast -- --test-threads=4 \
      || echo "WARNING: core tests reported failures or timed out")
