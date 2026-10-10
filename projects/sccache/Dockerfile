# syntax=docker/dockerfile:1
# sccache needs Rust >= rust-version in Cargo.toml, plus real C/C++ compilers for its
# integration tests and bubblewrap for the sccache-dist build sandbox.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang pkg-config libssl-dev cmake \
      bubblewrap redis-server memcached \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Fetch every crate so later builds work with --offline.
RUN cargo fetch --locked

# Build the client/server with all default storage backends and the dist client, and the
# sccache-dist scheduler/build server. Debug builds keep debug info and assertions.
RUN cargo build --locked --all-targets \
    && cargo build --locked --features dist-server --bin sccache-dist

# Compile (but do not run) the dist test suite too, so it is usable offline.
RUN cargo test --locked --features dist-tests --no-run

# Run the unit tests as a smoke check. Integration tests start a real sccache server and
# must run with --test-threads 1; see threat_model.md. Failures do not abort the build.
RUN (timeout 1800 cargo test --locked --lib --bins -- --test-threads 1 \
      || echo "WARNING: sccache unit tests reported failures")
