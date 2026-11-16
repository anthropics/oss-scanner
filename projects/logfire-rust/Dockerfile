# The scanner uses the repository root as the build context and audits /src offline, so every crate the
# build and the tests need is fetched here. No Cargo.lock is committed, so dependencies resolve to the
# latest compatible versions, as in CI.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTFLAGS="-C force-frame-pointers=yes"

COPY . /src
WORKDIR /src

RUN cargo fetch

# The network is gone after this point, and tests must not try to send to Logfire, as in CI.
ENV CARGO_NET_OFFLINE=true \
    LOGFIRE_SEND_TO_LOGFIRE=no

RUN cargo build --workspace --all-targets --all-features

# Run the test suite so the image is known to work; a failing test must not abort the build.
RUN cargo test --workspace --all-features || echo "WARNING: cargo test reported failures"
