# OSS Scanner build image for Core Lightning (https://github.com/ElementsProject/lightning).
# Installs build dependencies, Rust, uv/Python test environment, and bitcoind/bitcoin-cli so the
# scanner can build, run C and Rust unit tests, and run Python integration tests offline.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      autoconf \
      automake \
      bison \
      build-essential \
      ca-certificates \
      clang \
      curl \
      flex \
      gettext \
      git \
      gnupg \
      jq \
      libev-dev \
      libevent-dev \
      libffi-dev \
      libgmp-dev \
      libicu-dev \
      libpq-dev \
      libsodium-dev \
      libsqlite3-dev \
      libtool \
      lowdown \
      pkg-config \
      protobuf-compiler \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv \
      sqlite3 \
      wget \
      zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CARGO_HOME=/root/.cargo \
    RUSTUP_HOME=/root/.rustup \
    PATH="/root/.cargo/bin:/root/.local/bin:${PATH}"

RUN curl --proto '=https' --tlsv1.2 -fsSL https://astral.sh/uv/install.sh | sh \
    && curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable --component rustfmt

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install Bitcoin Core (bitcoind + bitcoin-cli) verified against CLN's bundled release keys so
# offline Python/regtest tests can start bitcoind without Internet access.
ARG BITCOIN_VERSION=27.1
RUN set -eu; \
    cd /tmp; \
    tarball="bitcoin-${BITCOIN_VERSION}-x86_64-linux-gnu.tar.gz"; \
    base_url="https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}"; \
    curl --proto '=https' --tlsv1.2 -fsSLO "${base_url}/${tarball}"; \
    curl --proto '=https' --tlsv1.2 -fsSLO "${base_url}/SHA256SUMS"; \
    curl --proto '=https' --tlsv1.2 -fsSLO "${base_url}/SHA256SUMS.asc"; \
    gpg --batch --quiet --import /src/contrib/keys/bitcoin/*; \
    gpg --batch --verify SHA256SUMS.asc SHA256SUMS; \
    sha256sum -c SHA256SUMS --ignore-missing; \
    tar xzf "${tarball}" --strip-components=1 -C /usr/local "bitcoin-${BITCOIN_VERSION}/bin/bitcoind" "bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli"; \
    rm -rf /tmp/bitcoin-* /tmp/SHA256SUMS* /root/.gnupg

# Pre-fetch Rust crates and Python virtual environment while network access is available.
RUN git config --global --add safe.directory /src \
    && git submodule update --init --recursive --depth 1 || true \
    && cargo fetch --locked \
    && uv sync --all-extras --all-groups

ENV CARGO_NET_OFFLINE=true \
    UV_OFFLINE=1 \
    CARGO_INCREMENTAL=0

# Build Core Lightning (C daemons + Rust plugins/crates) with debug info and frame pointers.
RUN ./configure --enable-rust --disable-valgrind \
    && uv run make -j"$(nproc)" COPTFLAGS="-g -Og -fno-omit-frame-pointer" \
    && cargo test --locked --workspace --no-run

# Run C and Rust unit tests non-fatally to verify the offline test environment.
RUN uv run make -j"$(nproc)" check-units || echo "WARNING: make check-units reported failures"
RUN cargo test --locked --workspace || echo "WARNING: cargo test reported failures"
