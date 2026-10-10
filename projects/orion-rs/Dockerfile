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

WORKDIR /src

RUN cargo install honggfuzz

RUN git clone https://github.com/orion-rs/orion.git && cd orion/ && mkdir -p ./.cargo/
RUN cd /src/orion \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN git clone https://github.com/orion-rs/orion-dudect && cd orion-dudect && mkdir -p ./.cargo/
RUN cd /src/orion-dudect \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN git clone https://github.com/orion-rs/orion-fuzz && cd orion-fuzz && mkdir -p ./.cargo/
RUN cd /src/orion-fuzz \
    && cargo generate-lockfile \
    && cargo fetch \
    && cargo vendor vendor > .cargo/config.toml

RUN cd /src/orion \
    && cargo test --all-features
