FROM rust:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config clang \
      sqlite3 libsqlite3-dev libglib2.0-dev libcairo2-dev \
      libgdk-pixbuf-2.0-dev libpango1.0-dev libgtk-4-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Debug build with frame pointers; fetch all crates while network is available.
ENV RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo fetch --locked \
    && cargo build --locked --all --all-targets

# Run the tests so we know the image works, but do not abort the build on failures.
RUN cargo test --locked --all --no-fail-fast || echo "WARNING: cargo test reported failures"
