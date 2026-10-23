# Scanner image for https://github.com/nimiq/core-rs-albatross (albatross): the Nimiq Proof-of-Stake node and its
# libraries.
#
# The audit runs offline, so this build fetches every crate in Cargo.lock, then builds the workspace in the dev profile
# (debug assertions and overflow checks on): every binary (nimiq-client, nimiq-rpc, nimiq-spammer, ...), the examples and
# every test binary. threat_model.md, next to this file, says how to run all of it.

# Latest stable Rust, which is what the repository's CI tests with (its MSRV is lower).
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive
# mdbx-sys builds libmdbx with clang and generates its bindings with bindgen, which needs libclang. openssl-sys links
# libssl. jinja2 and tomli are what scripts/devnet/devnet.py needs to start a local multi-validator network.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang libclang-dev lld cmake pkg-config libssl-dev python3 python3-jinja2 python3-tomli \
    && rm -rf /var/lib/apt/lists/*

# rustc already links x86_64 Linux targets with lld. Do the same on aarch64: GNU ld runs out of memory linking the
# debug test binaries in parallel.
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C link-arg=-fuse-ld=lld"

# cargo-nextest, which CI uses to run the tests.
RUN case "$(uname -m)" in x86_64) platform=linux ;; aarch64) platform=linux-arm ;; *) exit 1 ;; esac \
    && curl -fsSL "https://get.nexte.st/latest/${platform}" | tar -xzf - -C "${CARGO_HOME}/bin" \
    && cargo nextest --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never

# Every crate in Cargo.lock, for every target and feature, so later builds with other features or cfgs stay offline.
RUN cargo fetch --locked

# The workspace with default features, as CI's test job builds it: binaries, examples and every test binary. A step
# that fails fails the build, and primary_contact gets the log.
RUN cargo build --locked --workspace --bins --examples \
    && cargo nextest run --locked --workspace --no-run

# Run the tests so the log shows the image works, without letting a failure (or a slow test) abort the build.
RUN timeout 600 cargo nextest run --locked --workspace --no-fail-fast \
    || echo "WARNING: cargo nextest reported failures or timed out"

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
