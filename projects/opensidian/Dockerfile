# SPDX-License-Identifier: GPL-3.0-or-later
# Build image for Anthropic's OSS Scanner (https://github.com/anthropics/oss-scanner).
# The scanner builds this with the repository root as the build context. Network is only
# available during this build; the scan itself runs offline, so everything is fetched here.

# Pinned toolchain (Rust 1.98.0, the version the README documents) on Debian 13, a tested distro.
FROM docker.io/library/rust:1.98.0-slim-trixie@sha256:17d1ba895198f9934c6314ec5346a0d5115372f3243390c3d731e242f35c2f27

ENV DEBIAN_FRONTEND=noninteractive
# Build deps from README "Build from source", plus Xvfb so the app and tests can run headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential pkg-config git \
      libssl-dev libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev \
      xvfb xauth dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged build/test user: two tests (refused-write injection via chmod 0555, and the
# folder picker denying /root) are meaningless as root, which ignores file modes and has HOME=/root.
RUN useradd --create-home --uid 1000 --shell /bin/sh scanner \
    && chown -R scanner:scanner "$CARGO_HOME"

# scanner contract: the checkout lives inside the image, at /src
COPY --chown=scanner:scanner . /src
WORKDIR /src/src-tauri
USER scanner

# Release build as shipped, but with debug info, no symbol stripping and frame pointers.
ENV CARGO_PROFILE_RELEASE_DEBUG=true \
    CARGO_PROFILE_RELEASE_STRIP=none \
    RUSTFLAGS="-C force-frame-pointers=yes"

# Fetch every crate while the network is up, then build the app and the test binaries.
RUN cargo fetch --locked
RUN cargo build --release --locked
RUN cargo test --release --locked --no-run

# Run the tests so the image is known to work; a failing test must not abort the build.
RUN (xvfb-run -a cargo test --release --locked || echo "WARNING: cargo test reported failures")

# From here on there is no network: cargo must use what was fetched above.
ENV CARGO_NET_OFFLINE=true

# Back to root so the scanner can add its own tooling layers. Run the tests as the build user:
#   runuser -u scanner -- sh -c "cd /src/src-tauri && xvfb-run -a cargo test --release --locked"
USER root
# The app binary: /src/src-tauri/target/release/opensidian (run under xvfb-run, e.g.
# `xvfb-run -a target/release/opensidian /path/to/vault`).
