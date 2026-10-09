# OSS Scanner build for cryptsetup.
#
# Two builds are produced from the same checkout in /src:
#   /src/build       gcc, debugoptimized, -g -fno-omit-frame-pointer. Mirrors a distribution build;
#                    use it to run the upstream test suite (meson test -C /src/build).
#                    Tools: /src/build/src/{cryptsetup,veritysetup,integritysetup}
#   /src/build-asan  clang, AddressSanitizer + UndefinedBehaviorSanitizer, libFuzzer targets enabled.
#                    Use it to confirm memory-safety findings and to run the fuzzers:
#                      /src/build-asan/tests/fuzz/crypt2_load_fuzz
#                      /src/build-asan/tests/fuzz/crypt2_load_ondisk_fuzz
#                      /src/build-asan/tests/fuzz/crypt_load_misc_fuzz
#                    Tools: /src/build-asan/src/{cryptsetup,veritysetup,integritysetup}
#
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang libclang-rt-dev lld llvm meson ninja-build pkg-config \
      autoconf automake autopoint libtool gettext \
      libssl-dev libdevmapper-dev libpopt-dev uuid-dev libjson-c-dev libssh-dev \
      libblkid-dev libkeyutils-dev \
      sharutils dmsetup jq xxd expect keyutils netcat-openbsd passwd \
      openssh-client sshpass xz-utils tar file e2fsprogs util-linux kmod gdb \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# 1) Reference build (distribution-like: OpenSSL backend incl. Argon2, debug info, frame pointers).
RUN meson setup /src/build /src \
      --buildtype=debugoptimized \
      -Dc_args="-g -fno-omit-frame-pointer" \
      -Dasciidoc=disabled \
      -Dnls=false \
      -Dcrypto-backend=openssl \
      -Dargon-implementation=none \
    && meson compile -C /src/build

# 2) Sanitizer + fuzzer build (same OpenSSL backend incl. Argon2).
#    b_lundef=false is required when linking with -fsanitize=*.
RUN CC=clang CXX=clang++ meson setup /src/build-asan /src \
      --buildtype=debug \
      -Db_sanitize=address,undefined \
      -Db_lundef=false \
      -Dc_args="-g -fno-omit-frame-pointer -fno-sanitize-recover=undefined" \
      -Dcpp_args="-g -fno-omit-frame-pointer -fno-sanitize-recover=undefined" \
      -Dfuzz-targets=true \
      -Dcrypto-backend=openssl \
      -Dargon-implementation=none \
      -Dasciidoc=disabled \
      -Dnls=false \
    && meson compile -C /src/build-asan

# Sanitizer defaults for anyone running the ASan binaries in this image.
ENV ASAN_OPTIONS=detect_leaks=1:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# Smoke tests that need neither root device-mapper nor a kernel module: crypto vectors, wipe,
# utility units and exported-symbol checks. Failures are reported but never abort the build.
# The full suite (meson test -C /src/build) needs root, device-mapper and loop devices; it can be
# run inside the scanner's privileged VM.
RUN cd /src/build && (meson test --no-rebuild --print-errorlogs --timeout-multiplier 3 \
        vectors-test unit-wipe-test unit-utils-crypt-test run-all-symbols \
      || echo "WARNING: cryptsetup smoke tests reported failures")

# Quick sanity check that the sanitized fuzzers start (no crash on the empty input).
RUN for f in crypt2_load_fuzz crypt2_load_ondisk_fuzz crypt_load_misc_fuzz; do \
      /src/build-asan/tests/fuzz/$f -runs=1 >/dev/null 2>&1 \
        || echo "WARNING: fuzzer $f failed its smoke run"; \
    done
