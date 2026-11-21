# Scanner image for https://github.com/godot-pty/gpty.
#
# The audit runs offline, so this file fetches everything the build and the
# tests need while the network is available: the pinned FFmpeg, the pinned
# Godot 4.7.2 editor, every crate in both workspaces, cargo-fuzz and its
# nightly toolchain. x86-64 only: the Godot download and the FFmpeg prefix are
# the linux-x86_64 artifacts.

FROM node:22-bookworm-slim AS node

FROM rust:1.96.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CARGO_PROFILE_DEV_DEBUG=2 \
    CARGO_PROFILE_RELEASE_DEBUG=2 \
    CARGO_PROFILE_RELEASE_STRIP=false \
    CARGO_PROFILE_RELEASE_LTO=false \
    CARGO_INCREMENTAL=0

# Bounds memory during the build without reaching the audit environment.
ARG CARGO_BUILD_JOBS=4

# build-essential/nasm/pkg-config: scripts/media-deps compiles the pinned
# FFmpeg. clang + libclang-dev: ffmpeg-sys-the-third runs bindgen against its
# headers. The X11/GL/alsa/pulse/dbus/udev/fontconfig libraries are loaded by
# the Godot editor binary and by the headless GUT suite.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang curl git libclang-dev \
      libasound2 libdbus-1-3 libfontconfig1 libgl1 libpulse0 libudev1 \
      libx11-6 libxcursor1 libxi6 libxinerama1 libxkbcommon0 libxrandr2 \
      nasm pkg-config python3 unzip \
    && rm -rf /var/lib/apt/lists/*

# Node 22 for `node --test` in extensions/gpty-omp-events (its package.json
# requires node >= 20; Debian bookworm ships 18).
COPY --from=node /usr/local/bin/node /usr/local/bin/node

# Godot 4.7.2, the version .github/workflows/ci.yml pins. The release tag is
# mutable; this SHA512 is the pin (the workflows verify the same value).
RUN curl -fsSL -o /tmp/godot.zip \
      https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip \
    && echo "9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65  /tmp/godot.zip" | sha512sum -c - \
    && unzip -q /tmp/godot.zip -d /usr/local/bin \
    && mv /usr/local/bin/Godot_v4.7.2-stable_linux.x86_64 /usr/local/bin/godot \
    && chmod +x /usr/local/bin/godot \
    && rm /tmp/godot.zip \
    && godot --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The pinned FFmpeg prefix the GDExtension links. Its source and build trees
# are ~2 GB and are not needed at audit time.
RUN ./scripts/media-deps \
    && rm -rf dist/ffmpeg/src dist/ffmpeg/build-linux-x86_64

# What scripts/media-deps writes to dist/ffmpeg/linux-x86_64/env.sh, as ENV so
# every later step and the audit shell see it.
ENV FFMPEG_DIR=/src/dist/ffmpeg/linux-x86_64 \
    PKG_CONFIG_PATH=/src/dist/ffmpeg/linux-x86_64/lib/pkgconfig \
    LD_LIBRARY_PATH=/src/dist/ffmpeg/linux-x86_64/lib

# Fetch every crate and install the fuzzing toolchain before the network goes.
RUN cargo fetch --locked \
    && (cd fuzz && cargo fetch --locked) \
    && rustup toolchain install nightly-2026-11-01 --profile minimal \
    && cargo install cargo-fuzz --locked --version 0.13.2

# Everything is fetched; from here on the build proves the audit works offline.
ENV CARGO_NET_OFFLINE=true

# Debug build of every crate, binary and test target. The debug information is
# what an auditor debugs with. `--tests` builds the lib as a test unit and does
# not emit the cdylib, so gpty-gdext is built once more for
# target/debug/libgpty_gdext.so, the artifact godot/gpty.gdextension loads.
RUN cargo build --locked --workspace --bins --tests \
    && cargo build --locked -p gpty-gdext

# The seven libFuzzer targets. fuzz/ is its own workspace and CI builds them
# the same way.
RUN (cd fuzz && RUSTUP_TOOLCHAIN=nightly-2026-11-01 cargo fuzz build)

# Stage the GDExtension where godot/gpty.gdextension expects it, then import
# the project so later headless runs start from a ready cache.
RUN cp target/debug/libgpty_gdext.so godot/bin/libgpty_gdext.linux.x86_64.so \
    && godot --headless --path godot --import

# Run the suites so the log shows the image works; a failing test must not
# abort the build. gut-check is the same gate CI uses and judges the run, not
# just the exit code.
RUN (cargo test --locked --workspace || echo "WARNING: cargo test reported failures") \
    && (./scripts/gut-check || echo "WARNING: GUT reported failures") \
    && (cd extensions/gpty-omp-events && node --test || echo "WARNING: omp-events tests reported failures")

CMD ["bash"]
