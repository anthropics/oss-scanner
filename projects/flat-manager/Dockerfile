FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        pkg-config \
        cmake \
        perl \
        nasm \
        git \
        curl \
        libostree-dev \
        libglib2.0-dev \
        libpq-dev \
        flatpak \
        ostree \
        gnupg \
        postgresql \
        python3 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/gpg /usr/bin/gpg2

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:${PATH} \
    RUST_BACKTRACE=1

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable

COPY . /src
WORKDIR /src

RUN cargo fetch --locked

RUN cargo build --locked

RUN cargo build --release --locked

RUN cargo test --locked --no-run

RUN cargo test --locked || echo "WARNING: cargo test reported failures"
