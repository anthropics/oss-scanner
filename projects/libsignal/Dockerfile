# libsignal (https://github.com/signalapp/libsignal), the Rust core of Signal's protocol, cryptography and
# networking, with its bridges to Java, Swift and TypeScript.
#
# Only the Rust workspace is built, the way CI's Rust job builds it. The Java, Node and Swift wrappers are not: their
# Rust bridge crates are in the workspace, and the code above them adds little that parses untrusted input. The
# toolchain follows rust-toolchain, and protoc follows java/Dockerfile.
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
# clang and libclang are for boring-sys's bindgen; cmake builds BoringSSL.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip build-essential clang libclang-dev cmake pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# 1.29.2, newer than java/Dockerfile's 1.28.2, as rustup recommends after the eMudhra certificate incident.
ARG RUSTUP_VERSION=1.29.2
ARG RUSTUP_HASH=5be191e8c70a5007074254cb74d78dbfdd25cd5a61c27de7b8e5410122ec24f4
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH="/opt/cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/rustup-init \
      "https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/x86_64-unknown-linux-gnu/rustup-init" \
    && echo "$RUSTUP_HASH  /tmp/rustup-init" | sha256sum -c - \
    && chmod +x /tmp/rustup-init \
    && /tmp/rustup-init -y --profile minimal --default-toolchain none --no-modify-path \
    && rm /tmp/rustup-init

ARG PROTOC_VERSION=29.3
ARG PROTOC_HASH=3e866620c5be27664f3d2fa2d656b5f3e09b5152b42f1bedbf427b333e90021a
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/protoc.zip \
      "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VERSION}/protoc-${PROTOC_VERSION}-linux-x86_64.zip" \
    && echo "$PROTOC_HASH  /tmp/protoc.zip" | sha256sum -c - \
    && unzip -q -o /tmp/protoc.zip -d /usr/local bin/protoc 'include/*' \
    && rm /tmp/protoc.zip

# Scanner contract: tools/check builds this Dockerfile with the libsignal checkout as the build context, and the
# checkout must live inside the image, at /src.
COPY . /src
WORKDIR /src

# Installs the toolchain that rust-toolchain names (a stable release, which is what libsignal ships with; CI's nightly
# jobs are not needed to build), then fetches every crate in Cargo.lock, git dependencies included.
RUN rustup toolchain install "$(cat rust-toolchain)" --profile minimal \
    && cargo fetch --locked

# Build the workspace and every test binary, with all features, as CI's Rust job does. Cargo fetches nothing at test
# time, so building the tests is what lets them run offline during the scan.
RUN cargo build --locked --workspace --all-features \
    && cargo test --locked --workspace --all-features --no-run

# The scan has no network. Make every later cargo command offline, so that a forgotten --offline cannot stall on the
# registry.
ENV CARGO_NET_OFFLINE=true
