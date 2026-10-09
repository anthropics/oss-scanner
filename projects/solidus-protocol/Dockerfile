# Solidus Protocol: Cargo workspace of 21 crates (libp2p, RocksDB, BLS12-381).
# rust-toolchain.toml pins the stable channel plus rustfmt, clippy and the wasm32 target. rustup installs them on the
# first cargo call inside /src, which happens in this build, so the finished image needs no network.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang libclang-dev cmake pkg-config git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Debug info is on by default in the dev profile; frame pointers help the agent's debuggers and profilers.
ENV RUSTFLAGS="-C force-frame-pointers=yes" \
    CARGO_TERM_COLOR=never

# Fetch every crate now, while the network exists (this also installs the pinned toolchain).
RUN cargo fetch --locked

# Parallel jobs for cargo: two cores free once there are more than four, and one job per 3 GiB of memory, because the
# debug link of a test binary against RocksDB needs about 2 GiB and an out-of-memory kill takes the build host down.
RUN printf '%s\n' \
      '#!/bin/sh' \
      'N=$(nproc); [ "$N" -gt 4 ] && N=$((N - 2))' \
      'M=$(( $(sed -n "s/^MemTotal: *\([0-9]*\) kB/\1/p" /proc/meminfo) / 3145728 )); [ "$M" -lt 1 ] && M=1' \
      '[ "$N" -gt "$M" ] && N=$M' \
      'echo "$N"' > /usr/local/bin/cargo-jobs \
    && chmod +x /usr/local/bin/cargo-jobs

# Every library and binary must build. This step fails the image if one does not.
RUN cargo build --workspace --locked -j "$(cargo-jobs)"

# Test, bench and example binaries too, so the offline agent can run them without compiling. One test target in this
# repository (solidus-hotstuff2, tests/pop_committee.rs) reads a fixture that is outside the repository and cannot
# compile; --keep-going builds every other target.
RUN cargo build --workspace --all-targets --locked --keep-going -j "$(cargo-jobs)" \
    || echo "WARNING: some targets did not compile (expected: solidus-hotstuff2 pop_committee)"

# Smoke test only: a fast crate. A failing test must not abort the build.
RUN cargo test -p solidus-crypto --locked --offline || echo "WARNING: solidus-crypto tests reported failures"

# No network after this point: stop cargo from waiting on it.
ENV CARGO_NET_OFFLINE=true
