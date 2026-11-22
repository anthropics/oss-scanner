# Build context: the Ruffle repository root. Keep sources and Cargo caches for
# rebuilding reproducers after the scanner disconnects the network.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential clang cmake ninja-build pkg-config \
    python3 default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Match the stable toolchain used by Ruffle's Linux CI.
ENV RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo
ENV PATH="/opt/cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --profile minimal --default-toolchain stable \
    && rm /tmp/rustup-init.sh

WORKDIR /src
COPY . /src
RUN apt-get update \
    && xargs -r apt-get install -y --no-install-recommends < .github/linux-dependencies.txt \
    && rm -rf /var/lib/apt/lists/*

ENV CARGO_BUILD_JOBS=4 \
    CARGO_PROFILE_DEV_DEBUG=2 \
    CARGO_PROFILE_TEST_DEBUG=2

RUN cargo fetch --locked \
    && cargo build --locked -p ruffle_desktop \
    && cargo test --locked --no-run -p tests --features lzma,jpegxr,freetype \
    && cargo test --locked --no-run -p swf -p flv-rs -p naga-agal

# Verify that the parser tests can run without fetching more dependencies.
RUN cargo test --offline --locked -p swf -p flv-rs -p naga-agal
ENV CARGO_NET_OFFLINE=true
