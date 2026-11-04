# OSS Scanner build of chia_rs.
#
# The scanner builds this with the chia_rs checkout as the build context, so `COPY . /src` puts it at /src.
# Network access exists only while this file builds; the scan runs offline, so everything is fetched here.
#
# What is built: the whole workspace with all features in the dev profile (debug assertions and overflow checks on),
# every test binary, the Python extension (installed into /opt/venv), and the cargo-fuzz targets under crates/*/fuzz,
# with the nightly toolchain CI fuzzes with.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never

# Line-table debug info and frame pointers in every build, release and fuzz included, for usable stack traces.
# The workspace's release profile uses thin LTO; it is turned off here so release builds keep their debug info cheaply.
ENV RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer" \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    CARGO_PROFILE_RELEASE_STRIP=none \
    CARGO_PROFILE_RELEASE_LTO=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang pkg-config libssl-dev cmake python3 python3-dev python3-venv gdb strace \
    && rm -rf /var/lib/apt/lists/*

# Python venv for the chia_rs extension and its pytest suite (tests/).
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --quiet --upgrade pip && pip install --quiet 'maturin~=1.7' pytest

# The nightly CI fuzzes with (.github/workflows/build-crate.yml), and cargo-fuzz.
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

# The workspace with all features and every test binary, as CI's build-crate job builds it. A failing step fails the
# build, and primary_contact gets the log.
RUN cargo build --locked --workspace --all-features --all-targets \
    && cargo test --locked --workspace --all-features --no-run

# The Python extension, so tests/ and Python reproducers run against this checkout.
RUN maturin build --release --locked -m wheel/Cargo.toml -i /opt/venv/bin/python \
      --out /opt/wheels \
    && pip install --no-deps /opt/wheels/chia_rs-*.whl

# Fuzz targets, built but not run. A failure is reported but does not fail the build.
RUN for d in crates/*/fuzz; do \
      ( cd "$d/.." && cargo +"${FUZZ_NIGHTLY}" fuzz build ) || echo "WARNING: cargo fuzz build failed in $d"; \
    done

# Smoke tests so the log shows the image works; a failure does not fail the build.
RUN timeout 1200 cargo test --locked --workspace --all-features || echo "WARNING: cargo test reported failures"
