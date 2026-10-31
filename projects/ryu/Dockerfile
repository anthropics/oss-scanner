# Builds the open-source Ryu node: ryu-core (Apache-2.0, apps/core) and ryu-gateway (AGPL-3.0,
# apps/gateway). The scanner builds this with the amajorai/ryu checkout as the build context.
#
# Trixie, not bookworm: Core's ONNX Runtime dependency links against glibc 2.38+ symbols, which
# Debian 12 does not ship (see the comment at the top of the repository's root Dockerfile).
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
# Debug builds keep full debug info; frame pointers make backtraces usable.
ENV CARGO_TARGET_DIR=/src/target \
    RUSTFLAGS="-C force-frame-pointers=yes"

# Fetch every crate (including dev-dependencies) while the network is still available.
RUN cargo fetch --locked --manifest-path apps/gateway/Cargo.toml \
 && cargo fetch --locked --manifest-path apps/core/Cargo.toml

# The shipped Core binary enables the Wasmtime/WASI sandbox, so build that configuration.
RUN cargo build --locked --manifest-path apps/gateway/Cargo.toml \
 && cargo build --locked --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime

# Compile the test binaries now so they can run offline during the audit.
RUN cargo test --locked --no-run --manifest-path apps/gateway/Cargo.toml \
 && cargo test --locked --no-run --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime

ENV CARGO_NET_OFFLINE=true \
    RYU_PROFILE=dev \
    RYU_KEYCHAIN=off \
    RYU_DIR=/tmp/ryu-scan

# Run the cheap tests so we know the image works, but never let a failing test abort the build.
RUN (cargo test --locked --manifest-path apps/gateway/Cargo.toml -- --test-threads=4 \
      || echo "WARNING: gateway tests reported failures") \
 && (cargo test --locked --manifest-path apps/core/Cargo.toml --features sandbox-wasmtime -- --test-threads=4 \
      || echo "WARNING: core tests reported failures")
