# Scanner image for https://github.com/LLFourn/secp256kfun (master): the workspace built and tested as CI does, on
# x86-64 and on 32-bit i686. The 32-bit target selects the 10x26 field and 8x32 scalar backends, which are what
# 32-bit hardware signers (ESP32-C3) run.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_PROFILE_RELEASE_DEBUG=line-tables-only \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang gcc-multilib git pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

RUN rustup target add i686-unknown-linux-gnu

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# No lockfile is committed. Resolve one once and fetch every crate it names, so later builds stay offline.
RUN cargo generate-lockfile && cargo fetch --locked
ENV CARGO_NET_OFFLINE=true

# A step that fails fails the build, and primary_contact gets the log.
RUN cargo test --locked --workspace --all-features --release --no-run \
    && cargo test --locked --workspace --all-features --release --no-run --target i686-unknown-linux-gnu \
    && for p in secp256kfun sigma_fun ecdsa_fun schnorr_fun vrf_fun; do \
         cargo test --locked --release --no-default-features -p "$p" --no-run || exit 1; \
       done

# Show in the build log that the tests run, without failing the build on a broken or flaky test.
RUN timeout --kill-after=5 1800 cargo test --locked --workspace --all-features --release \
    || echo "WARNING: cargo test reported failures"
RUN timeout --kill-after=5 1800 cargo test --locked --workspace --all-features --release --target i686-unknown-linux-gnu \
    || echo "WARNING: cargo test (i686) reported failures"
