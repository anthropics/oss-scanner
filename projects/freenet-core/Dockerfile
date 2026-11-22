# Scanner image for https://github.com/freenet/freenet-core (main): the freenet node (crates/core), its fdev developer
# tool, and the test binaries CI runs.
#
# The audit runs offline, so this build installs the toolchain rust-toolchain.toml pins (with the wasm32 target that
# contracts compile to), fetches every crate in Cargo.lock, then builds the workspace binaries and every test binary
# with the feature set CI's Linux test job uses, so both share one set of dependency artifacts. threat_model.md, next
# to this file, says how to run all of it.

FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive
# clang and cmake cover native build scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang cmake pkg-config \
    && rm -rf /var/lib/apt/lists/*

# cargo-nextest, which CI runs the suite with. .config/nextest.toml holds the per-test timeouts.
RUN case "$(uname -m)" in x86_64) platform=linux ;; aarch64) platform=linux-arm ;; *) exit 1 ;; esac \
    && curl -fsSL "https://get.nexte.st/latest/${platform}" | tar -xzf - -C "${CARGO_HOME}/bin" \
    && cargo nextest --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The environment CI's Linux test job sets. RUST_MIN_STACK matches CI because some simulation tests recurse deeply.
# Line-table debug info keeps file and line numbers in backtraces while cutting build time and image size.
ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    RUST_LOG=error \
    RUST_MIN_STACK=268435456 \
    FREENET_BACKOFF_BASE_SECS=5 \
    CARGO_TARGET_DIR=/src/target \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_PROFILE_TEST_DEBUG=line-tables-only \
    FREENET_FEATURES=trace,websocket,redb,wasmtime-backend,testing \
    PATH=/src/target/debug:$PATH

# The toolchain and targets rust-toolchain.toml names, then every crate in Cargo.lock for every target, so the test
# harness can still compile contracts to wasm32 once the network is gone.
RUN rustup toolchain install && rustc --version && cargo fetch --locked

# The freenet and fdev binaries (into target/debug, which is on PATH), then every test binary, both with CI's test
# features. freenet-ping-app is left out: its tests link a second freenet-stdlib, which current linkers reject
# (https://github.com/freenet/freenet-core/issues/5950). A step that fails fails the build, and primary_contact gets
# the log. Incremental compilation is off for this step only: its cache is a third of target/ and makes the image slow
# to export, while later rebuilds in the scanner still get it. Run the suite with:
#   cargo nextest run --workspace --exclude freenet-ping-types --exclude freenet-ping-app \
#     --no-default-features --features "$FREENET_FEATURES" --profile ci -E 'not test(blocked_peers)'
RUN export CARGO_INCREMENTAL=0 \
    && cargo build --locked --workspace --exclude freenet-ping-types --exclude freenet-ping-app \
      --no-default-features --features "$FREENET_FEATURES" \
    && cargo nextest run --locked --workspace --exclude freenet-ping-types --exclude freenet-ping-app \
      --no-default-features --features "$FREENET_FEATURES" --no-run

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
