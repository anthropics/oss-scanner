# syntax=docker/dockerfile:1
# Native Rust workspace. libudev/libusb/libdbus back the HID, serial and BLE (BlueZ) hardware
# managers; cmake and clang build the statically linked SDL3 used by the gamepad manager.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1 \
    RUSTFLAGS="-C force-frame-pointers=yes"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang cmake pkg-config \
      libudev-dev libusb-1.0-0-dev libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Cargo.lock is not committed upstream; resolve one here and fetch every crate so later builds
# work with --offline.
RUN cargo generate-lockfile && cargo fetch --locked

# Debug build of the default workspace members (everything except the wasm32-only crate),
# including the intiface-engine binary, examples, and all test binaries.
RUN cargo build --locked --all-targets \
    && cargo test --locked --no-run

# Smoke test. Failures do not abort the build.
RUN (timeout 1800 cargo test --locked \
      || echo "WARNING: buttplug tests reported failures")
