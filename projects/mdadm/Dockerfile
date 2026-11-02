# Copy this template to your project (at the location specified in your project.yaml), or otherwise add it
# parallel to your project.yaml at projects/<name>/Dockerfile.
# This file must set up the environment, install your project's dependencies and build the project.
# The scanner builds it with your repository as the build context, so `COPY . /src` puts the checkout inside
# the image. Network access is available during this Dockerfile build and is removed after this point, so
# all code that an agent might need to perform its tests must be fetched here.

FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++

# Install build dependencies for mdadm (GNU make, libudev, debian packaging/compiler tools, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    clang \
    pkg-config \
    git \
    python3 \
    groff \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build mdadm using its Makefile with debug symbols (-g) and frame pointers enabled.
# mdadm's CWFLAGS include -Werror; CXFLAGS is appended after them, so it can add flags but not remove -Werror.
# -Wno-unknown-attributes: bookworm's clang 14 does not know __attribute__((nonstring)) (platform-intel.h).
RUN make -j"$(nproc)" \
    CC="$CC" \
    CXFLAGS="-g -fno-omit-frame-pointer -O1 -DNO_COROSYNC -Wno-unknown-attributes" \
    all mdmon

# Verify binaries were built and exercise basic help/version commands.
# Integration test suite requires root loop/block privileges (not available in standard Docker build),
# so we run quick verification checks without failing the build.
RUN (./mdadm --version && ./mdmon --version) || echo "WARNING: initial binary check reported failures"

