# Scanner environment, not a production image. Keep source and build tools.
# Build verification is pending; see the enrollment PR.
FROM rust:1.96-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_NET_OFFLINE=false \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    BRASSCLAW_DISABLE_OS_KEYCHAIN=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential clang llvm-dev libclang-dev cmake pkg-config \
    libssl-dev curl ca-certificates git python3 python3-yaml \
    libicu72 libxml2 libreadline8 libzstd1 zlib1g \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
# Fetch workspace/dev dependencies online; embedded PostgreSQL and pgvector
# are fetched and verified by the product build script during compilation.
RUN cargo fetch --locked
RUN cargo build --locked -p brassclaw -p brassclaw_monty_host --bins
ENV CARGO_NET_OFFLINE=true \
    BRASSCLAW_MONTY_WORKER_PATH=/src/target/debug/monty_worker
# PostgreSQL cannot run as root. The scanner can use this account for tests.
RUN useradd --create-home --shell /bin/bash scanner \
    && chown -R scanner:scanner /src /usr/local/cargo
CMD ["bash"]
