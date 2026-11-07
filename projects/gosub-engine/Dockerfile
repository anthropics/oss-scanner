FROM rust:trixie
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

# Compile the tests but do not run them here: the sandbox and process-isolation tests need user namespaces,
# which `docker build` does not grant. They pass in the scanner's privileged container: `cargo test --all`.
RUN cargo test --locked --all --no-run
