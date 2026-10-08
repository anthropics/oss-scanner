# Builds FerroCrypt for OSS Scanner: the library and CLI (the Cargo workspace),
# the desktop app, and the fuzz targets. The scan runs offline, so every
# dependency the builds and tests need is fetched here.
FROM rust:1-trixie

ENV DEBIAN_FRONTEND=noninteractive

# Libraries the desktop app's GUI toolkit (Slint) builds against, as in the project's CI.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libfontconfig-dev libfreetype-dev libwayland-dev \
      libxcb-shape0-dev libxcb-xfixes0-dev libxkbcommon-dev \
    && rm -rf /var/lib/apt/lists/*

# The fuzz targets need nightly and cargo-fuzz.
RUN rustup toolchain install nightly --profile minimal \
    && cargo install cargo-fuzz

COPY . /src
WORKDIR /src

# Library and CLI. A build failure fails the image; failing tests only warn.
RUN cargo fetch --locked && cargo build --workspace --all-targets --locked
RUN cargo test --workspace --locked --no-fail-fast -- --test-threads=1 \
    || echo "WARNING: workspace tests reported failures"

# The desktop app is outside the workspace, with its own lock file.
RUN cd ferrocrypt-desktop && cargo fetch --locked && cargo build --all-targets --locked
RUN cd ferrocrypt-desktop && { cargo test --locked --no-fail-fast -- --test-threads=1 \
    || echo "WARNING: desktop tests reported failures"; }

# So are the fuzz targets.
RUN cd ferrocrypt-lib/fuzz && cargo +nightly fetch && cargo +nightly fuzz build

# The scan has no network, so cargo must not try to reach one.
ENV CARGO_NET_OFFLINE=true
