# OSS Scanner build for libffi (https://github.com/libffi/libffi).
#
# This file sits next to project.yaml in the oss-scanner repository. The scanner copies it into a fresh
# clone of libffi's master branch and builds it with that clone as the build context, so the checkout
# lands at /src. The network is available only while this file builds; the scan itself runs offline, so
# everything a reproducer might need (compiler, sanitizer runtimes, headers, the libffi sources) is
# installed here.
#
# libffi is an autotools project. Two out-of-tree (VPATH) builds are produced from the same /src checkout:
#
#   /src/build        clang, -g -O1 with frame pointers. A plain debuggable build. The full DejaGnu test
#                     suite (make check) runs against it, so the image log shows the build works.
#   /src/build-asan   clang, AddressSanitizer + UndefinedBehaviorSanitizer, -g with frame pointers. The
#                     sanitized libffi the scanner uses to confirm memory-safety and UB findings and to
#                     build reproducers offline. libffi's own test cases are compiled by the DejaGnu
#                     harness without the sanitizer flags, so the suite is not run against this tree; the
#                     sanitizer runtimes (libclang-rt-dev) are present for reproducers the scanner builds.
#
# Base is debian:trixie, matching libffi's own CI (.ci/Containerfile.debian): its libtool 2.5.x bootstraps
# the autotools build cleanly.
FROM docker.io/library/debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    ASAN_OPTIONS=abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# libclang-rt-dev holds clang's sanitizer runtimes. autogen.sh needs autoconf/automake/libtool and makeinfo
# (texinfo); the test suite needs dejagnu (runtest). libltdl-dev is required for its ltdl.m4, which defines
# the LT_SYS_SYMBOL_USCORE macro libffi's configure.ac uses (the base libtool package does not ship it).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang llvm libclang-rt-dev \
      autoconf automake libtool libltdl-dev texinfo dejagnu pkg-config gdb \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Regenerate configure and friends from the checkout (libffi ships no configure in git).
RUN ./autogen.sh

# Reference build: debuggable, no sanitizers, so the DejaGnu suite links cleanly. Shared + static.
# (configure prints a harmless "clang: error: unsupported option '-print-multi-os-directory'" while probing
# for a multilib path with a GCC-only flag; it falls back cleanly and the build and tests proceed.)
RUN mkdir -p /src/build && cd /src/build \
    && ../configure CC=clang CXX=clang++ CFLAGS="-g -O1 -fno-omit-frame-pointer" \
         --enable-shared --enable-static \
    && make -j"$(nproc)"

# Run the full test suite, but never let a failing test abort the image; the log stays for the scanner.
RUN cd /src/build && (make check -j"$(nproc)" || echo "WARNING: libffi make check reported failures") \
    && (cat /src/build/*/testsuite/libffi.log 2>/dev/null | tail -40 || true)

# Sanitizer build of the library (ASan + UBSan, non-recoverable UB), for reproducing findings.
RUN mkdir -p /src/build-asan && cd /src/build-asan \
    && ../configure CC=clang CXX=clang++ \
         CFLAGS="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=undefined" \
         LDFLAGS="-fsanitize=address,undefined" \
         --enable-shared --enable-static \
    && make -j"$(nproc)"
