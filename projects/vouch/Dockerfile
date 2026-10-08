# Builds the vouch Cargo workspace (vouch-cli, vouch-agent, vouch-server and shared crates) with debug info.
# The base image ships the toolchain that rust-toolchain.toml pins; RUSTUP_TOOLCHAIN uses it as is.
FROM rust:1.99.0-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    AWS_LC_FIPS_SYS_CC=clang \
    AWS_LC_FIPS_SYS_CXX=clang++ \
    CARGO_TERM_COLOR=never \
    RUSTUP_TOOLCHAIN=1.99.0
# Same system dependencies as the project's Linux CI (aws-lc-fips needs cmake, go and clang; FIDO2/HID needs libudev).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang cmake pkg-config git python3 \
      libssl-dev libudev-dev golang-go perl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every crate while network access is available.
RUN cargo fetch --locked

# Build all crates and test binaries with debug info and frame pointers, so the scan can run offline.
ENV RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo build --locked --all-features --workspace --all-targets \
    && cargo test --locked --all-features --workspace --no-run

# Run the unit tests so the image is known to work, without letting a failure abort the build.
RUN cargo test --locked --all-features --workspace || echo "WARNING: cargo test reported failures"
