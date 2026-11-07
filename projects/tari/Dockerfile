# Scanner image for https://github.com/tari-project/tari (development).
#
# The audit runs offline, so this build fetches every crate in Cargo.lock, then builds the workspace in the dev profile
# (debug assertions and overflow checks on, line-tables-only debug info): the libraries, the binaries (minotari_node,
# minotari_console_wallet, minotari_miner, minotari_merge_mining_proxy, ...) and every test binary. threat_model.md,
# next to this file, says how to run them.

# rust-toolchain.toml pins the stable channel, which is what CI builds with.
FROM rust:1-bookworm
# The whole image build, including exporting it, has 40 minutes, and target/ for every crate and test binary is large.
# No incremental caches and line-tables-only debug info keep it small enough to export in time; backtraces still carry
# file and line numbers.
ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The system dependencies CI installs (sqlite, openssl, hidapi/udev for the Ledger transport, and an upstream protoc
# new enough for proto3 `optional`).
RUN apt-get update \
    && bash scripts/install_ubuntu_dependencies.sh \
    && rm -rf /var/lib/apt/lists/*

# Every crate in Cargo.lock, so later builds with other features or cfgs stay offline.
RUN cargo fetch --locked

# The workspace: libraries, binaries and every test binary. A step that fails fails the build, and primary_contact
# gets the log.
RUN cargo build --locked --workspace --lib --bins \
    && cargo test --locked --workspace --no-run

# Run the unit tests so the log shows the image works, without letting a failure abort the build. `--lib` keeps the
# cucumber suite (integration_tests, which spins up whole networks) out, and matches the package set built above so
# nothing recompiles. The scanner bounds the whole image build, so the run is cut off after 3 minutes. Some tari_core
# tests share state and can flake in parallel; run them with `-- --test-threads=1` when investigating.
RUN timeout 180 cargo test --locked --workspace --lib \
    || echo "WARNING: cargo test reported failures or was cut off"
