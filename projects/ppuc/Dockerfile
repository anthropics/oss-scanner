# ppuc: the PPUC host applications (ppuc-pinmame, ppuc-menu, ppuc-backbox).
# Mirrors the linux-x64 job in .github/workflows/ppuc.yml, which runs on ubuntu-24.04.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential cmake pkg-config git curl unzip zip python3 file \
      autoconf automake libtool nasm bison flex patchelf \
      libudev-dev libpipewire-0.3-dev libwayland-dev wayland-protocols libxml2-utils libdecor-0-dev \
      liburing-dev libasound2-dev libpulse-dev libaudio-dev libjack-dev libsndio-dev \
      libx11-dev libxext-dev libxrandr-dev libxcursor-dev libxfixes-dev libxi-dev libxss-dev libxtst-dev \
      libxkbcommon-dev libdrm-dev libgbm-dev libgl1-mesa-dev libgles2-mesa-dev libegl1-mesa-dev \
      libdbus-1-dev libibus-1.0-dev libgpiod-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The platform scripts are per architecture; pick the one matching the build machine.
RUN case "$(uname -m)" in \
      x86_64) echo x64 ;; \
      aarch64|arm64) echo aarch64 ;; \
      *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;; \
    esac > /etc/ppuc-arch

# The maintainers' build, unchanged: stages every pinned dependency into third-party/ (libppuc, libsdldmd,
# PinMAME, SDL3, Lua, flite, espeak-ng, the VPX media plugins, ...), builds the three executables and
# packages them with their runtime libraries into /src/ppuc. This is the only step that needs the network.
RUN ./platforms/linux/"$(cat /etc/ppuc-arch)"/build.sh

# PPUC's own sources again with debug info and frame pointers, plus the unit tests, against the
# dependencies staged above.
RUN cmake -S /src -B /src/build-debug \
      -DPLATFORM=linux -DARCH="$(cat /etc/ppuc-arch)" \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-g -fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-g -fno-omit-frame-pointer" \
      -DPPUC_BUILD_TESTS=ON \
    && cmake --build /src/build-debug -j"$(nproc)" \
      --target ppuc-pinmame ppuc-menu ppuc-backbox ppuc_tests

# The plugin smoke test and the stub plugin it loads. Kept apart and non-fatal: CI builds only ppuc_tests on
# Linux, so these two targets are not guaranteed to compile there.
RUN cmake --build /src/build-debug -j"$(nproc)" --target FakeCtlPlugin ppuc_plugin_smoke \
      || echo "WARNING: ppuc_plugin_smoke did not build"

# Run the tests so a broken image is visible in the log, without letting a failing test abort the build.
RUN ctest --test-dir /src/build-debug --output-on-failure --timeout 300 \
      || echo "WARNING: ctest reported failures"
