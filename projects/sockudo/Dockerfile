# syntax=docker/dockerfile:1
# Sockudo is a Rust workspace (edition 2024, rust-version 1.95). The server binary is the
# `sockudo` package in crates/sockudo-server. Native deps: libpq / libmariadb for the SQL
# backends, protobuf + cmake + clang for the queue/adapter clients (Kafka, Pulsar, ...).
FROM rust:1.99-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang libclang-dev pkg-config cmake \
      libssl-dev libpq-dev libmariadb-dev protobuf-compiler libprotobuf-dev \
      redis-server curl \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Fetch every crate so later builds work with --offline. .cargo/config.toml adds
# `--cfg tokio_unstable`, which must stay in effect for all builds.
RUN cargo fetch --locked

# Debug build of the server with every feature (all adapters, backends, V2, AI Transport,
# push, Ably compat, MCP). Debug builds keep debug info and assertions.
RUN cargo build --locked -p sockudo --features full

# Compile (but do not run) every workspace test target so they are usable offline.
RUN cargo test --locked --workspace --no-run

# Smoke-run the unit tests. A few of them need Redis on the default ports (6379, and 16379 /
# REDIS_URL), so start local servers for the duration of this step. Integration tests that need
# other live backends (Postgres, NATS, Redis Cluster, ...) are left for later. Failures do not
# abort the build.
RUN redis-server --port 6379 --daemonize yes --save "" --appendonly no \
    && redis-server --port 16379 --daemonize yes --save "" --appendonly no \
    && (timeout 2400 cargo test --locked --workspace --lib --no-fail-fast \
          || echo "WARNING: sockudo unit tests reported failures"); \
    redis-cli -p 6379 shutdown nosave; redis-cli -p 16379 shutdown nosave; true
