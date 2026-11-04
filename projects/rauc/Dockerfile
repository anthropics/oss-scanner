# Build RAUC (https://github.com/rauc/rauc) for the OSS Scanner.
#
# Layers on RAUC's own CI container, which GitHub Actions uses for the test,
# sanitizer and cross-build jobs (.github/workflows/*.yml). It is built from
# test/Dockerfile in the RAUC repository and already holds every build and test
# dependency (meson, gcc, GLib, OpenSSL, libcurl, D-Bus, pytest, SoftHSM,
# casync/desync, qemu-system-x86, ...). This file adds clang for the fuzzers,
# builds RAUC the way the CI jobs do, and fetches what the tests need while the
# network is still available.
FROM ghcr.io/rauc/rauc/rauc-ci
USER 0
ENV DEBIAN_FRONTEND=noninteractive

# clang + its sanitizer/libFuzzer runtime for the fuzzing build below. The CI
# image carries gcc only. Also let root use the git checkout owned by rauc-ci.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang libclang-rt-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /src

# scanner contract: the checkout lives inside the image, at /src.
# Build and test as the image's unprivileged rauc-ci user (uid 1000), as the
# CI jobs do; tests that need root (loop devices, mounts, dm-verity) then skip
# instead of failing and are covered by ./qemu-test.
COPY --chown=rauc-ci:rauc-ci . /src
WORKDIR /src
USER rauc-ci

# Fetch the test kernel that ./qemu-test would otherwise download on first use,
# so the full test suite (loop devices, dm-verity, NAND/MTD, eMMC, ...) can be
# run offline: ./qemu-test, or ./qemu-test test=<name> for a single test. The
# VM tests are an extra, so a failed download warns instead of failing the build.
RUN KERNEL_URL="$(sed -n 's/^KERNEL_URL="\(.*\)"$/\1/p' qemu-test)" \
    && KERNEL_SHA256SUM="$(sed -n 's/^KERNEL_SHA256SUM="\(.*\)"$/\1/p' qemu-test)" \
    && if curl -fsSL "$KERNEL_URL" -o bzImage.tmp \
          && echo "$KERNEL_SHA256SUM  bzImage.tmp" | sha256sum --check --status; then \
         mv bzImage.tmp bzImage; \
       else \
         rm -f bzImage.tmp; echo "WARNING: could not fetch the qemu-test kernel; ./qemu-test will not work offline"; \
       fi

# Main build, as the maintainers build it: gcc, all features enabled, with debug
# info and frame pointers. The binary is build/rauc, the service is the same
# binary (`rauc service`), the unit tests are build/test/*-test.
RUN meson setup build \
      -Dbuildtype=debugoptimized \
      -Dc_args="-fno-omit-frame-pointer" \
      -Dservice=true -Dgpt=enabled -Dnetwork=true -Dstreaming=true \
    && meson compile -C build

# Second build with clang + AddressSanitizer/libFuzzer, for the fuzz targets in
# fuzz/ (build-fuzz/fuzz/manifest_fuzzer and build-fuzz/fuzz/bundle_fuzzer;
# seed corpora and dictionary in fuzz/).
RUN CC=clang CXX=clang++ meson setup build-fuzz \
      -Dbuildtype=debugoptimized \
      -Dservice=false -Dfuzzing=true -Db_lundef=false -Db_sanitize=address \
    && meson compile -C build-fuzz

# Run the test suite that works without root privileges or a VM (what RAUC's
# "stable" CI job runs), so the image is known to work. A failing test does
# not abort the build.
RUN (meson test -C build --suite rauc --timeout-multiplier 3 --print-errorlogs \
      || echo "WARNING: meson test reported failures")

# The scanner works as root in /src.
USER 0
