FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    build-essential \
    binutils-dev \
    libunwind-dev \
    libblocksruntime-dev \
    liblzma-dev \
    pkg-config \
    libssl-dev \
    git \
    clang \
    cmake \
    pkg-config \
    ninja-build \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain stable \
    && rustup --version \
    && cargo --version \
    && rustc --version
RUN rustup toolchain install nightly

COPY . /src
WORKDIR /src

# Vendor all dependencies for offline builds
RUN mkdir -p ./.cargo/ \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN mkdir -p /opt/ && cargo install honggfuzz

RUN cd /opt/ && git clone https://github.com/orion-rs/orion-dudect && mkdir -p /opt/orion-dudect/.cargo/
RUN cd /opt/orion-dudect \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN cd /opt/ && git clone https://github.com/orion-rs/orion-fuzz && mkdir -p /opt/orion-fuzz/.cargo/
RUN cd /opt/orion-fuzz \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN cargo test --all-features
