# OSS Scanner build for Password Safe (https://github.com/pwsafe/pwsafe).
#
# Password Safe is a password manager written in C++ that stores credentials in
# an Twofish / AES-256 encrypted database file (.psafe3 / .psafe4). This build
# targets the wxWidgets (Linux/macOS) UI and the core library together.
#
# The scanner will find the following after the build:
#   /src/build/src/ui/wxWidgets/pwsafe   -- the main GUI binary
#   /src/build/src/ui/cli/pwsafe-cli     -- the command-line interface
#   /src/build/src/test/coretest         -- GoogleTest suite for the core library
#                                           (crypto, file-format parsers, key derivation)
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang libclang-rt-14-dev cmake ninja-build pkg-config git python3 \
      libwxgtk3.2-dev \
      libssl-dev \
      libmagic-dev \
      uuid-dev \
      libqrencode-dev \
      libxerces-c-dev \
      libykpers-1-dev \
      libx11-dev \
      libxt-dev \
      libxtst-dev \
      libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# C.UTF-8 is the built-in glibc locale
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Pre-fetch googletest in its own layer so cmake's ExternalProject_Add finds the
# source directory already populated. cmake then does a fast `git fetch + checkout`
# instead of a full `git clone` inside execute_process, which hangs silently in
# some Docker network environments because it has no progress output.
RUN mkdir -p /src/build && \
    git clone --depth 1 --branch v1.17.0 \
      https://github.com/google/googletest.git \
      /src/build/googletest-src

# Build with RelWithDebInfo so debug info and frame pointers are present for the
# scanner. gtest is built from source (GTEST_BUILD=ON, the default).
RUN cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-g -fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-g -fno-omit-frame-pointer" \
      -DXML_XERCESC=ON \
    && cmake --build /src/build -j"$(nproc)"

# Run the core library test suite. These test AES, Twofish, SHA-1/256,
# HMAC-SHA-1/256, key wrapping, and the V3/V4 file-format parsers.
# Failures are printed but do not abort the build.
RUN cd /src/build && \
    (ctest --output-on-failure -j"$(nproc)" --timeout 300 \
     || echo "WARNING: ctest reported failures")
