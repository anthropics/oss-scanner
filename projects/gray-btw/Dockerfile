FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config libssl-dev libsqlite3-dev clang cmake build-essential python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Debug profile keeps debug info + frame pointers for the audit.
RUN cargo build --workspace || cargo build --release || cargo build
RUN (timeout 600 cargo test --workspace || timeout 600 cargo test || echo "WARNING: cargo test reported failures")
