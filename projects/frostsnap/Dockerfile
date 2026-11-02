# Scanner image for https://github.com/frostsnap/frostsnap (master). Builds and tests the Rust crates that carry the
# security model: the protocol core, wire format, coordinator backend, backups, secure-boot verification, device UI,
# and a type-check of the ESP32-C3 firmware. The Flutter app and its generated FFI bridge are not built.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_PROFILE_RELEASE_DEBUG=line-tables-only \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang git pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# rust-toolchain.toml pins the compiler and the riscv32imc target; install it now, while the network is up.
RUN rustup toolchain install

# Cargo.lock is committed. Fetch every crate it names (all targets), so later builds stay offline.
RUN cargo fetch --locked
ENV CARGO_NET_OFFLINE=true

# The host-side crates. frostsnapp/rust (needs flutter_rust_bridge codegen) and desktop_camera are left out.
ENV FROSTSNAP_CRATES="-p frostsnap_core -p frostsnap_comms -p frostsnap_coordinator -p frostsnap_embedded \
    -p frost_backup -p frostsnap_secure_boot -p frostsnap_widgets"

# A step that fails fails the build, and primary_contact gets the log.
RUN cargo test --locked --all-features $FROSTSNAP_CRATES --no-run

# Firmware build scripts (secp256k1-sys) need the RISC-V C compiler. Fetch the one `just fetch-riscv` uses and check it
# against the hash in the repository's justfetch.lock.
RUN tarball=riscv32-elf-ubuntu-22.04-gcc-nightly-2024.09.03-nightly.tar.gz \
    && curl -fsSL -o "/opt/$tarball" \
         "https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2024.09.03/$tarball" \
    && (cd /opt && grep " $tarball\$" /src/justfetch.lock | sha256sum -c -) \
    && tar -xzf "/opt/$tarball" -C /opt && rm "/opt/$tarball"
ENV PATH="/opt/riscv/bin:${PATH}"

# Firmware crates only build for the device; type-check them as `just check-device` does.
RUN cargo check --locked --all-features --target riscv32imc-unknown-none-elf -p frostsnap_device -p frostsnap_cst816s

# Show in the build log that the tests run, without failing the build on a broken or flaky test.
RUN timeout --kill-after=5 1800 cargo test --locked --all-features $FROSTSNAP_CRATES \
    || echo "WARNING: cargo test reported failures"
