FROM rust:trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config clang \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Debug build with frame pointers; fetch all crates while network is available.
ENV RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo fetch --locked \
    && cargo build --locked --all-features --all-targets

# Run the tests so we know the image works, but do not abort the build on failures.
RUN cargo test --locked --all-features --no-fail-fast || echo "WARNING: cargo test reported failures"
