# libzedmd: the ZeDMD communication library, with the zedmd-client and zedmd-test command-line tools.
# Mirrors the linux jobs in .github/workflows/libzedmd.yml, which run on ubuntu-24.04.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential cmake pkg-config git curl unzip python3 \
      autoconf automake libtool libgpiod-dev \
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

# Build and stage the pinned dependencies into third-party/: cargs, libserialport, sockpp and the
# header-only libframeutil. This is the only step that needs the network.
RUN BUILD_TYPE=Release ./platforms/linux/"$(cat /etc/ppuc-arch)"/external.sh

# The library (shared and static) and its command-line tools, with debug info and frame pointers.
RUN cmake -S /src -B /src/build \
      -DPLATFORM=linux -DARCH="$(cat /etc/ppuc-arch)" \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-g -fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-g -fno-omit-frame-pointer" \
    && cmake --build /src/build -j"$(nproc)"

# The same again under AddressSanitizer and UBSan (the project's own ENABLE_SANITIZERS option, Debug only).
RUN cmake -S /src -B /src/build-san \
      -DPLATFORM=linux -DARCH="$(cat /etc/ppuc-arch)" \
      -DCMAKE_BUILD_TYPE=Debug \
      -DENABLE_SANITIZERS=ON \
    && cmake --build /src/build-san -j"$(nproc)"

# There is no automated test suite: zedmd-test needs a ZeDMD device. Start the client once so a binary that
# cannot find its libraries shows up in the log, without letting that abort the build. (--help rather than
# --version: the latter prints the versions but exits non-zero.)
RUN /src/build/zedmd-client --help > /dev/null || echo "WARNING: zedmd-client did not start"
