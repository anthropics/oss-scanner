# Scanner image for https://github.com/Jagalite/superseedr (main): the superseedr crate (library and binary) and the
# fuzz workspace member.
#
# The audit runs offline, so this build fetches every crate in Cargo.lock, then builds the crate with all features in the
# dev profile (debug assertions and overflow checks on): the library, the binary and every test target.
# threat_model.md, next to this file, says how to exercise it.

# rust-toolchain.toml pins the toolchain; rustup installs it on first use below.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang lld pkg-config libssl-dev git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The library's unit-test binary is large. Full debug info and many parallel rustc jobs run a 4-6 GB builder out of memory,
# so keep line tables (enough for backtraces) and cap the jobs.
ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_BUILD_JOBS=2

# Install the pinned toolchain, then every crate in Cargo.lock (including the fuzz member's), so later builds stay offline.
RUN rustup show active-toolchain || rustup toolchain install \
    && cargo fetch --locked

# All features, as CI builds it: library, binary and every test binary. A step that fails fails the build, and
# primary_contact gets the log.
RUN cargo build --locked --all-features --lib --bins \
    && cargo test --locked --all-targets --all-features --no-run

# Run the tests so the log shows the image works, without letting a failure (or a test that needs the Internet) abort
# the build. The scanner allows 45 minutes for the whole Dockerfile, so cap the run at 15.
RUN timeout 900 cargo test --locked --all-targets --all-features --no-fail-fast \
    || echo "WARNING: cargo test reported failures"

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true

CMD ["bash"]
