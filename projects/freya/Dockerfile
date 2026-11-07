FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_BUILD_JOBS=2 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1 \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates clang cmake curl git ninja-build pkg-config python3 \
        libssl-dev libglib2.0-dev libgtk-3-dev libudev-dev libxdo-dev \
        libwebkit2gtk-4.1-dev libasound2-dev libfontconfig1-dev libfreetype6-dev \
        libgl1-mesa-dev libegl1-mesa-dev libwayland-dev libxkbcommon-dev \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain none

COPY . /src
WORKDIR /src

RUN git submodule update --init --recursive

# Cargo uses the toolchain pinned in rust-toolchain.toml.
RUN cargo fetch --locked \
    && cargo build --locked --workspace --features freya/all-debug \
    && cargo build --locked --package freya --features devtools \
    && cargo test --locked --no-run --workspace \
        --exclude examples --exclude web --exclude freya-web --features all-tests

ENV CARGO_NET_OFFLINE=true
