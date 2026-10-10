# MetasequoiaIME (水杉输入法): Rust workspace (engine, input runtime, C host ABI, tools)
# plus the Linux native hosts (IBus engine and Fcitx5 addon, C++), built as
# platforms/linux/build-container.sh does. Windows/macOS/mobile hosts need their
# own SDKs and are not built here; their shared Rust crates are.
FROM rust:1.97.1-bookworm@sha256:0e2bcaef56d041a486784e54104a81aebe0da44bd03019bd70bc0401e42e4a97
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git cmake ninja-build pkg-config python3 clang \
      libasound2-dev libssl-dev \
      libwebkit2gtk-4.1-dev libgtk-3-dev libsoup-3.0-dev libjavascriptcoregtk-4.1-dev \
      libibus-1.0-dev libxkbcommon-dev nlohmann-json3-dev \
      libwayland-dev wayland-protocols libx11-dev libxfixes-dev libxrandr-dev \
      libfcitx5core-dev libfcitx5utils-dev libfcitx5config-dev libcairo2-dev \
      dbus dbus-bin \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV CARGO_TARGET_DIR=/src/target \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer"

# Install the pinned toolchain from rust-toolchain.toml and fetch every crate
# now: the scan runs without network.
RUN rustup show active-toolchain && cargo fetch --locked

# Rust workspace (default members: every library crate plus the CLIs), with tests compiled.
RUN cargo build --locked \
    && cargo build --locked -p msime-dict-builder -p msime-pack-tool -p msime-backend-engine \
    && cargo test --locked --no-run

# Linux native hosts (IBus + Fcitx5) against the debug host library.
RUN cargo build --locked -p msime-host-api \
    && cmake -S platforms/linux -B /src/build/linux -G Ninja \
         -DCMAKE_BUILD_TYPE=Debug \
         -DMSIME_ENABLE_FCITX5=ON \
         -DMSIME_HOST_LIBRARY=/src/target/debug/libmsime_host_api.so \
    && cmake --build /src/build/linux -j"$(nproc)"

# Cheap tests, so the image is known to work; failures do not abort the build.
RUN (cargo test --locked --no-fail-fast -- --test-threads="$(nproc)" || echo "WARNING: cargo test reported failures") \
    && (ctest --test-dir /src/build/linux --output-on-failure -j"$(nproc)" --timeout 300 || echo "WARNING: ctest reported failures")
