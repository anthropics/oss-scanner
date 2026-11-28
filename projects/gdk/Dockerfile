# OSS Scanner build image for GDK (https://github.com/Blockstream/gdk).
# Mirrors docker/debian/Dockerfile for the native Linux GCC + Rust build and unit tests,
# pre-fetching all C/C++ and Cargo dependencies so the scan runs completely offline.
FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      autoconf \
      automake \
      autotools-dev \
      build-essential \
      ca-certificates \
      clang \
      cmake \
      curl \
      git \
      libssl-dev \
      libtool \
      libtool-bin \
      ninja-build \
      pkg-config \
      python-is-python3 \
      python3 \
      python3-dev \
      python3-venv \
      swig \
      unzip \
    && rm -rf /var/lib/apt/lists/*

ENV CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    RUST_VERSION=1.85.0 \
    PATH="/usr/local/cargo/bin:/root/venv/bin:/root/.local/bin:${PATH}"

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain "${RUST_VERSION}"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install uv and Python build requirements (from tools/requirements.txt).
RUN ./tools/install_uv.sh \
    && uv venv /root/venv \
    && uv pip install --python /root/venv --require-hashes -r tools/requirements.txt

# Build C/C++ third-party dependencies once into /prebuild/gcc.
ENV GDK_KEEP_DOWNLOADS=1
RUN mkdir -p /prebuild/gcc \
    && ./tools/builddeps.sh --gcc --prefix /prebuild/gcc --parallel "$(nproc)"

ENV OPENSSL_DIR=/prebuild/gcc \
    OPENSSL_STATIC=True

# Pre-fetch Rust crates so cargo runs offline during the scan.
RUN cargo fetch --locked --manifest-path /src/subprojects/gdk_rust/Cargo.toml
ENV CARGO_NET_OFFLINE=true \
    CARGO_INCREMENTAL=0

# Build GDK C++ library + tests (matching CI's gcc release + tests configuration).
RUN ./tools/build.sh --gcc --buildtype release --no-deps-rebuild \
      --external-deps-dir /prebuild/gcc --parallel "$(nproc)" --enable-tests

# Pre-compile Rust unit tests offline.
RUN cargo test --locked --no-run --manifest-path /src/subprojects/gdk_rust/Cargo.toml

# Run C++ and Rust unit tests non-fatally to verify offline execution.
RUN cd /src/build-gcc && (ctest --output-on-failure || echo "WARNING: ctest reported failures")
RUN cargo test --locked --lib --manifest-path /src/subprojects/gdk_rust/Cargo.toml || echo "WARNING: cargo test reported failures"
