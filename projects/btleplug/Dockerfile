# syntax=docker/dockerfile:1
# Cross-platform BLE library. On Linux it talks to BlueZ over D-Bus (libdbus). A JDK lets the
# Android JNI support code (src/droidplug/jni_utils) build and run against the host JVM.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1 \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    JAVA_HOME=/usr/lib/jvm/default-java
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang pkg-config \
      libdbus-1-dev default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Fetch every crate so later builds work with --offline.
RUN cargo fetch --locked

# Debug build of the library, examples and test binaries, with and without the optional
# serde and JNI host-test features.
RUN cargo build --locked --all-targets \
    && cargo build --locked --all-targets --all-features \
    && cargo test --locked --no-run

# Unit tests and JNI host tests as a smoke check. The integration tests in tests/ are #[ignore]d
# and need a hardware test peripheral. Failures do not abort the build.
RUN (timeout 900 cargo test --locked \
      || echo "WARNING: btleplug unit tests reported failures") \
    && (timeout 900 ./scripts/run-jni-tests.sh \
      || echo "WARNING: btleplug JNI host tests reported failures")
