FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_TOOLCHAIN=1.98.1 \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        curl \
        git \
        libclang-dev \
        libdw-dev \
        libssl-dev \
        libudev-dev \
        pkg-config \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# protoc 21.5 matches docker/builder/builder.Dockerfile. Bookworm's protobuf-compiler does not.
RUN arch="$(uname -m | sed -e 's/arm64/arm_64/g' -e 's/aarch64/aarch_64/g')" \
    && curl -fsSL -o /tmp/protoc.zip "https://github.com/protocolbuffers/protobuf/releases/download/v21.5/protoc-21.5-linux-${arch}.zip" \
    && unzip -o /tmp/protoc.zip -d /usr/local bin/protoc 'include/*' \
    && chmod +x /usr/local/bin/protoc \
    && rm /tmp/protoc.zip

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain 1.98.1 --profile minimal --component clippy

# rust-toolchain.toml also lists rust-docs. RUSTUP_TOOLCHAIN stops an offline cargo from fetching it.
COPY . /src
WORKDIR /src

RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=0 \
    CARGO_PROFILE_TEST_DEBUG=line-tables-only

# Binaries for the commands in threat_model.md. Full debug objects do not fit the build disk.
RUN cargo test -p aptos-crypto --offline --lib --no-run \
    && cargo test -p aptos-safety-rules --offline --lib --no-run \
    && cargo test -p aptos-consensus-types --offline --lib --no-run \
    && cargo test -p e2e-move-tests --offline --no-run \
    && cargo test -p aptos-transactional-test-harness --test tests --offline --no-run \
    && cargo test -p aptos-consensus --offline --lib --no-run
