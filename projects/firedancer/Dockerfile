# Copy this template to your project (at the location specified in your project.yaml), or otherwise add it
# parallel to your project.yaml at projects/<name>/Dockerfile.
# This file must set up the environment, install your project's dependencies and build the project.
# The scanner builds it with your repository as the build context, so `COPY . /src` puts the checkout inside
# the image. Network access is available during this Dockerfile build and is removed after this point, so
# all code that an agent might need to perform its tests must be fetched here.

# OSS Scanner build of Firedancer (https://github.com/firedancer-io/firedancer), the Solana validator client
# written in C. The scan that follows this build runs offline on a small machine with 2 CPUs and 8 GB of memory.
#
# The checkout is built three times under /src/build, each with -O3, -g2 and frame pointers
# (config/extra/with-debug.mk):
#
#   gcc         GCC 14 with MACHINE=linux_gcc_x86_64 (-march=haswell, AVX2). This is the GCC configuration the
#               bug bounty covers, and it runs on any recent x86-64 CPU.
#   gcc-avx512  GCC 14 with MACHINE=linux_gcc_icelake, which adds the AVX-512 code paths that production
#               validators run for ed25519 signature checks, Reed-Solomon, SHA and AES. It needs a CPU with
#               AVX-512 IFMA.
#   clang-san   Clang 19 with MACHINE=linux_clang_x86_64 and EXTRAS="asan ubsan fuzz", which builds the unit
#               tests and libFuzzer harnesses with ASan, UBSan and Firedancer's handholding checks. It runs on
#               any recent x86-64 CPU.
#
# Each build directory has unit tests in unit-test/ and fuzz harnesses in fuzz-test/, and the two GCC builds also
# have bin/. threat_model.md explains how to run them in this image, where there are no huge pages, so tests need
# --page-sz normal.
#
# Nothing is built with MACHINE=native, because the image is built on one machine and scanned on another.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive

# Packages, and what each one is for:
#   build-essential       libc headers and binutils, including the ar and ranlib the build uses
#   gcc, g++, make        the two GCC builds
#   clang, llvm,          the sanitizer build. libclang-rt-dev holds the ASan, UBSan and libFuzzer runtimes, and
#   libclang-rt-dev       llvm provides llvm-symbolizer so that sanitizer reports show symbolized stacks.
#   lld                   the linker Firedancer's build prefers. config/base.mk links with mold or lld when one of
#                         them is installed, and falls back to GNU ld otherwise.
#   ca-certificates, git  carried over from templates/Dockerfile. git also lets the scan search the history to
#                         check whether a bug is already known
#   python3               Firedancer's code generators (make seccomp-policies and the src/**/generate scripts)
#   pkg-config            carried over from templates/Dockerfile, although Firedancer's build does not use it
#   gdb, file, xxd        debugging and looking at crash inputs
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential gcc g++ make clang lld llvm libclang-rt-dev \
      git python3 pkg-config gdb file xxd \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the project as its maintainers build it, with debug info (-g) and frame pointers. A step that fails fails the
# build, and primary_contact gets the log.
#
# The builds use Firedancer's own make targets, where `make all` builds the binaries, libraries, headers, unit
# tests and fuzz harnesses, and -Otarget keeps each target's compiler output together in the log.
#
# gcc-avx512 is built before gcc because each `make ... all` also copies the binaries it builds into /src/build
# (for example /src/build/firedancer), so the last build wins, and those copies should be the portable ones.
RUN make -j"$(nproc)" -Otarget MACHINE=linux_gcc_icelake CC=gcc BUILDDIR=gcc-avx512 all
RUN make -j"$(nproc)" -Otarget MACHINE=linux_gcc_x86_64 CC=gcc BUILDDIR=gcc all
# The sanitizer build only needs the unit tests and fuzz harnesses, because the scan target is the GCC build and
# the sanitizers are there to help find bugs.
RUN make -j"$(nproc)" -Otarget MACHINE=linux_clang_x86_64 CC=clang BUILDDIR=clang-san \
      EXTRAS="asan ubsan fuzz" unit-test fuzz-test

# Run the cheap tests so you know the image works, but do not let a failing test abort the build. Leave anything worth
# exercising (binaries, test drivers, examples) where threat_model.md says it is.
#
# This runs a few unit tests, a short libFuzzer run and the binary's --version. The AVX-512 build is left out
# because the build machine may not support AVX-512.
RUN for t in gcc/unit-test/test_sha256 gcc/unit-test/test_ed25519 gcc/unit-test/test_txn_parse \
             clang-san/unit-test/test_txn_parse; do \
      build/$t --log-path "" >/dev/null 2>&1 && echo "ok    $t" || echo "WARN  $t failed"; \
    done; \
    build/clang-san/fuzz-test/fuzz_txn_parse -runs=10000 -artifact_prefix=/tmp/ >/dev/null 2>&1 \
      && echo "ok    clang-san/fuzz-test/fuzz_txn_parse" || echo "WARN  clang-san/fuzz-test/fuzz_txn_parse failed"; \
    build/gcc/bin/firedancer --version || echo "WARN  gcc/bin/firedancer --version failed"

# The checks above only print warnings, so this step fails the build if anything the scan relies on is missing.
RUN set -eu; \
    fail() { echo "ENVIRONMENT ASSERTION FAILED: $*" >&2; exit 1; }; \
    for b in gcc gcc-avx512; do [ -x build/$b/bin/firedancer ] || fail "build/$b/bin/firedancer is missing"; done; \
    for b in gcc gcc-avx512 clang-san; do \
      [ -s build/$b/unit-test/automatic.txt ] || fail "build/$b has no unit tests"; \
      [ -x build/$b/fuzz-test/fuzz_txn_parse ] || fail "build/$b has no fuzz harnesses"; \
    done; \
    cmp -s build/firedancer build/gcc/bin/firedancer || fail "build/firedancer is not the portable gcc build"; \
    echo "environment assertions passed"
