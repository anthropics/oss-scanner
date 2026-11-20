# OSS Scanner build image for Blockstream App Desktop / Green Qt (https://github.com/Blockstream/green_qt).
# Mirrors ci/linux-x86_64/Dockerfile using public Qt 6.11.2 installation via aqtinstall (instead
# of a private QT_INSTALLER_JWT_TOKEN) and builds with the dev preset (ENABLE_SENTRY=OFF) + tests.
FROM ubuntu:22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      autoconf \
      automake \
      bluez \
      build-essential \
      ca-certificates \
      ccache \
      clang-12 \
      curl \
      git \
      libasound2 \
      libasound2-dev \
      libbluetooth-dev \
      libc++-12-dev \
      libcap-dev \
      libclang-12-dev \
      libd3dadapter9-mesa-dev \
      libdbus-1-dev \
      libegl1-mesa-dev \
      libfontconfig1-dev \
      libfreetype6-dev \
      libgl1-mesa-dev \
      libgles2-mesa-dev \
      libnspr4 \
      libnss3 \
      libnss3-dev \
      libpulse-dev \
      libtool \
      libudev-dev \
      libunwind-dev \
      libwayland-dev \
      libx11-dev \
      libx11-xcb-dev \
      libxcb-cursor-dev \
      libxcb-glx0-dev \
      libxcb-icccm4-dev \
      libxcb-image0-dev \
      libxcb-keysyms1-dev \
      libxcb-randr0-dev \
      libxcb-render-util0-dev \
      libxcb-shape0-dev \
      libxcb-shm0-dev \
      libxcb-sync-dev \
      libxcb-util-dev \
      libxcb-xfixes0-dev \
      libxcb-xinerama0-dev \
      libxcb-xinput-dev \
      libxcb-xkb-dev \
      libxcomposite-dev \
      libxcursor-dev \
      libxdamage-dev \
      libxdamage1 \
      libxext-dev \
      libxfixes-dev \
      libxi-dev \
      libxkbcommon-dev \
      libxkbcommon-x11-dev \
      libxkbfile-dev \
      libxkbfile1 \
      libxrandr-dev \
      libxrender-dev \
      libxtst-dev \
      linux-libc-dev \
      llvm-12-dev \
      nasm \
      ninja-build \
      pkg-config \
      protobuf-compiler \
      python3-pip \
      python3-venv \
      unzip \
      wget \
      xvfb \
      yasm \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives \
      --install /usr/bin/clang clang /usr/bin/clang-12 20 \
      --slave /usr/bin/clang++ clang++ /usr/bin/clang++-12

# Install CMake >= 3.26 (matching ci/linux-x86_64/setup.sh) and Qt 6.11.2 via aqtinstall.
RUN wget -q https://github.com/Kitware/CMake/releases/download/v3.26.0-rc3/cmake-3.26.0-rc3-linux-x86_64.sh \
    && chmod +x cmake-3.26.0-rc3-linux-x86_64.sh \
    && ./cmake-3.26.0-rc3-linux-x86_64.sh --skip-license --prefix=/usr \
    && rm cmake-3.26.0-rc3-linux-x86_64.sh \
    && pip3 install --no-cache-dir aqtinstall \
    && aqt install-qt linux desktop 6.11.2 linux_gcc_64 -O /qt \
         -m qt5compat qtconnectivity qtmultimedia qtserialport qtpositioning qtwebengine qtwebview qtwebchannel

# Install Rust toolchains matching ci/linux-x86_64/setup.sh.
ENV RUSTUP_HOME=/root/.rustup \
    CARGO_HOME=/root/.cargo \
    PREFIX=/depends/linux-x86_64 \
    HOST=linux \
    ARCH=x86_64
ENV PKG_CONFIG_PATH="${PREFIX}/lib/pkgconfig" \
    CMAKE_INSTALL_PREFIX="${PREFIX}" \
    CMAKE_PREFIX_PATH="${PREFIX}" \
    PATH="/qt/6.11.2/gcc_64/bin:${PREFIX}/bin:/root/.cargo/bin:${PATH}"

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --default-toolchain 1.88.0 \
    && rustup toolchain install 1.85.0-x86_64-unknown-linux-gnu

WORKDIR /tmp/deps

FROM base AS hidapi
COPY tools/buildlibusb.sh tools/buildhidapi.sh tools/
RUN tools/buildlibusb.sh && tools/buildhidapi.sh

FROM base AS countly
COPY tools/buildcountly.sh tools/
RUN tools/buildcountly.sh || (rm -rf build && sleep 5 && tools/buildcountly.sh)

FROM base AS gdk
COPY tools/buildgdk.sh tools/
RUN tools/buildgdk.sh --static || (rm -rf build && sleep 5 && tools/buildgdk.sh --static)

FROM base AS zxing
COPY tools/buildzxing.sh tools/
RUN tools/buildzxing.sh || (rm -rf build && sleep 5 && tools/buildzxing.sh)

FROM base AS kdsa
COPY tools/buildkdsingleapplication.sh tools/
RUN tools/buildkdsingleapplication.sh

FROM base AS libserialport
COPY tools/buildlibserialport.sh tools/
RUN tools/buildlibserialport.sh --disable-shared || (rm -rf build && sleep 5 && tools/buildlibserialport.sh --disable-shared)

FROM base AS gpgme
COPY tools/buildgpgme.sh tools/
RUN tools/buildgpgme.sh

FROM base AS leveldb
COPY tools/buildleveldb.sh tools/
RUN tools/buildleveldb.sh || (rm -rf build && sleep 5 && tools/buildleveldb.sh)

FROM base AS lwk
COPY tools/buildlwk.sh tools/
RUN tools/buildlwk.sh || (rm -rf build && sleep 5 && tools/buildlwk.sh)

FROM base AS glsdk
COPY tools/buildglsdk.sh tools/
RUN tools/buildglsdk.sh || (rm -rf build && sleep 5 && tools/buildglsdk.sh)

FROM base
COPY --from=hidapi /depends /depends
COPY --from=countly /depends /depends
COPY --from=gdk /depends /depends
COPY --from=zxing /depends /depends
COPY --from=kdsa /depends /depends
COPY --from=libserialport /depends /depends
COPY --from=gpgme /depends /depends
COPY --from=leveldb /depends /depends
COPY --from=lwk /depends /depends
COPY --from=glsdk /depends /depends

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV CARGO_NET_OFFLINE=true \
    CARGO_INCREMENTAL=0

# Build Blockstream App Desktop + unit tests using the dev preset (ENABLE_SENTRY=OFF).
RUN qt-cmake --preset dev -DBUILD_TESTING=ON \
    && cmake --build build -j"$(nproc)"

# Run unit tests offscreen non-fatally to verify the offline test setup.
RUN QT_QPA_PLATFORM=offscreen ctest --test-dir /src/build --output-on-failure || echo "WARNING: ctest reported failures"
