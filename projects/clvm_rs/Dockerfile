# OSS Scanner build of clvm_rs (crate clvmr).
#
# The scanner builds this with the clvm_rs checkout as the build context, so `COPY . /src` puts it at /src.
# Network access exists only while this file builds; the scan runs offline, so everything is fetched here.
#
# What is built: the workspace in the dev and release profiles with every test binary, the feature variants CI tests
# (counters, pre-eval, allocator-debug, no-fastpath), the Python extension (installed into /opt/venv), and the
# cargo-fuzz targets in fuzz/.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never

# Line-table debug info and frame pointers in every build, release and fuzz included, for usable stack traces.
# The crate's release profile uses thin LTO; it is turned off here so release builds keep their debug info cheaply.
ENV RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer" \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    CARGO_PROFILE_RELEASE_STRIP=none \
    CARGO_PROFILE_RELEASE_LTO=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang pkg-config libssl-dev python3 python3-dev python3-venv gdb strace \
    && rm -rf /var/lib/apt/lists/*

# Python venv for the clvm_rs extension and its tests.
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --quiet --upgrade pip && pip install --quiet 'maturin~=1.7' pytest

# A nightly for cargo-fuzz (CI uses the latest nightly; pinned here so the image is reproducible).
ARG FUZZ_NIGHTLY=nightly-2026-01-12
RUN rustup toolchain install "${FUZZ_NIGHTLY}" --profile minimal \
    && cargo +"${FUZZ_NIGHTLY}" install cargo-fuzz --locked

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# rust-toolchain.toml pins the stable toolchain; the first cargo call installs it while the network is up.
RUN cargo --version && rustc --version

# Every crate in Cargo.lock, for every target and feature. From here on cargo must not reach a registry, so the
# build itself shows the scan can run offline.
RUN cargo fetch --locked
ENV CARGO_NET_OFFLINE=true

# The workspace as CI's build-test job builds it, plus every test binary for each feature variant it tests. A failing
# step fails the build, and primary_contact gets the log.
RUN cargo build --locked --workspace --exclude clvm_rs-fuzz --all-targets \
    && cargo test --locked --no-run \
    && cargo test --locked --release --no-run \
    && for f in counters pre-eval allocator-debug no-fastpath openssl; do \
         cargo test --locked --features="$f" --no-run || exit 1; \
       done

# The Python extension, for Python reproducers.
RUN maturin build --release --locked -m wheel/Cargo.toml -i /opt/venv/bin/python \
      --out /opt/wheels \
    && pip install --no-deps /opt/wheels/clvm_rs-*.whl

# Fuzz targets, built but not run. A failure is reported but does not fail the build.
RUN cargo +"${FUZZ_NIGHTLY}" fuzz build || echo "WARNING: cargo fuzz build failed"

# Smoke tests so the log shows the image works; a failure does not fail the build.
RUN timeout 1200 cargo test --locked --release || echo "WARNING: cargo test reported failures"
