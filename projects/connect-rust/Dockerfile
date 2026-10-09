# Scanner image for https://github.com/connectrpc/connect-rust.
#
# The audit runs offline, so this build installs the toolchain, fetches every crate, downloads the ConnectRPC
# conformance runner, and compiles the workspace, its tests and the conformance binaries. threat_model.md, next to this
# file, says how to run each of them.
# x86-64 only: the protoc download below is the linux-x86_64 release.

# Stable Rust, which is what the repository's CI builds and tests with. The image already has curl, git and a C
# toolchain; curl is also what the example test scripts use.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# cmake and clang are for the C dependencies (aws-lc-sys, zstd-sys). Packages are fetched over HTTPS.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends unzip clang cmake pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# protoc, at the version that the repository's CI pins (PROTOC_VERSION in .github/workflows/ci.yml).
ARG PROTOC_VERSION=33.5
ARG PROTOC_SHA256=24e58fb231d50306ee28491f33a170301e99540f7e29ca461e0e80fd1239f8d1
RUN curl -fsSL -o /tmp/protoc.zip \
      "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VERSION}/protoc-${PROTOC_VERSION}-linux-x86_64.zip" \
    && echo "${PROTOC_SHA256}  /tmp/protoc.zip" | sha256sum -c - \
    && unzip -q -o /tmp/protoc.zip 'bin/*' 'include/*' -d /usr/local \
    && rm /tmp/protoc.zip \
    && protoc --version

# CI also checks the client for wasm32.
RUN rustup target add wasm32-unknown-unknown

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# Every crate that the workspace depends on, for all targets, and the conformance runner at the version the script pins.
RUN cargo fetch \
    && ./conformance/scripts/download-conformance.sh \
    && test -x ./conformance/bin/connectconformance

# The workspace, its tests, and the release conformance server and client. A step that fails fails the build, and
# primary_contact gets the log.
RUN cargo build --workspace --all-features \
    && cargo test --workspace --all-features --no-run \
    && cargo build --release -p connectrpc-conformance

# Run the tests and one conformance suite so the log shows the image works, without letting a failure abort the build.
RUN (timeout 1200 cargo test --workspace --all-features || echo "WARNING: cargo test reported failures") \
    && (timeout 600 ./conformance/bin/connectconformance --mode server --conf conformance/config/connect-only.yaml \
          -- ./target/release/conformance-server || echo "WARNING: the conformance runner reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
