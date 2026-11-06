# Builds adk-rust the way its pull-request tier does: the 1.95.0 toolchain that
# rust-toolchain.toml pins, the apt packages .github/workflows/ci.yml installs,
# the Linux `wild` linker sections stripped from .cargo/config.toml (only the
# devenv shell provides that linker), then every workspace crate with its tests,
# benches and in-crate examples. Network access ends after this file, so
# `cargo fetch` keeps every crate in Cargo.lock inside the image and any
# feature combination builds offline.
FROM rust:1.95.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_INCREMENTAL=0 \
    CARGO_TERM_COLOR=never \
    CMAKE_POLICY_VERSION_MINIMUM=3.5 \
    PROTOC=/usr/bin/protoc \
    RUSTFLAGS="-C force-frame-pointers=yes"

# protoc for lance's build script, libdbus for adk-cli's keyring dependency,
# cmake and the ALSA/udev headers for the audio and realtime crates, python3
# for the adk-sandbox process-execution tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang libclang-dev cmake pkg-config protobuf-compiler \
      libdbus-1-dev libasound2-dev libudev-dev libssl-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# cargo-nextest is the workspace's test runner (.config/nextest.toml).
RUN case "$(uname -m)" in \
      x86_64) arch=linux ;; \
      aarch64) arch=linux-arm ;; \
      *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac \
    && curl -fsSL --retry 3 "https://get.nexte.st/latest/$arch" | tar zxf - -C "$CARGO_HOME/bin" \
    && cargo nextest --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# rust-toolchain.toml lists clippy, rustfmt and rust-analyzer; installing them
# here means rustup never reaches for the network during a scan.
RUN rustup show active-toolchain && rustup component add clippy rustfmt rust-analyzer

# Plain Linux hosts have no `wild` linker: the same sed as .github/actions/setup-rust.
RUN sed -i '/\[target\.x86_64-unknown-linux-gnu\]/,/^$/d' .cargo/config.toml \
    && sed -i '/\[target\.aarch64-unknown-linux-gnu\]/,/^$/d' .cargo/config.toml \
    && sed -i "/\[target\.'cfg(all(target_os/,/^$/d" .cargo/config.toml

# Every crate in Cargo.lock, for every platform and optional feature, so
# `cargo build -p <crate> --features <features>` works without a network.
RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true

# The default-feature workspace with its tests, benches and in-crate examples:
# the scope of the PR tier's clippy and nextest jobs. The dev profile keeps full
# debug info. Jobs are bounded by memory because the largest crates need about
# 3 GiB each.
RUN jobs=$(( $(awk '/MemTotal/ { print int($2 / 1024 / 1024) }' /proc/meminfo) / 3 )); \
    [ "$jobs" -lt 1 ] && jobs=1; \
    [ "$jobs" -gt "$(nproc)" ] && jobs=$(nproc); \
    cargo build --workspace --all-targets --locked --jobs "$jobs"

# The cheap check that the image works. A failing test is reported, not fatal;
# the test binaries stay in target/debug for the scanner.
RUN timeout 900 cargo nextest run --workspace --no-fail-fast --locked \
    || echo "WARNING: nextest reported failures"
