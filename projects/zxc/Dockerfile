# OSS Scanner build for ZXC (https://github.com/hellobertrand/zxc).
#
# Three builds, all from the checkout at /src:
#
#   /src/build         RelWithDebInfo, no sanitizer: the library, the `zxc` CLI and the test programs as users get them.
#   /src/build-asan    The same targets under ASan + UBSan.
#   /src/build-fuzz    Every libFuzzer target from tests/fuzz under ASan + UBSan, built by .clusterfuzzlite/build.sh, the
#                      script ClusterFuzzLite and OSS-Fuzz use. Binaries are named zxc_fuzzer_<target>.
#
# ZXC_NATIVE_ARCH is off so the binaries do not depend on the CPU of the build machine. SIMD variants are still built and
# selected at run time.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# clang is clang-18 on this release; libclang-rt-18-dev holds its sanitizer and libFuzzer runtimes.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang libclang-rt-18-dev llvm cmake ninja-build pkg-config git python3 gdb \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-fno-omit-frame-pointer" \
      -DZXC_NATIVE_ARCH=OFF \
    && cmake --build /src/build -j"$(nproc)"

RUN cmake -S /src -B /src/build-asan -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-O1 -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=undefined" \
      -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined" \
      -DZXC_NATIVE_ARCH=OFF \
    && cmake --build /src/build-asan -j"$(nproc)"

# build.sh compiles with paths relative to the checkout and leaves its objects there, so they are removed afterwards.
RUN mkdir -p /src/build-fuzz \
    && SANITIZE="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined,fuzzer-no-link -fno-sanitize-recover=undefined" \
       CFLAGS="$SANITIZE" CXXFLAGS="$SANITIZE" LIB_FUZZING_ENGINE="-fsanitize=fuzzer" OUT=/src/build-fuzz \
       bash .clusterfuzzlite/build.sh \
    && rm -rf obj obj_scalar objvariants

# Cheap checks: unit, conformance and golden tests, the CLI suite, and each fuzzer replaying the conformance vectors. A
# failure is reported but does not abort the build. LeakSanitizer needs ptrace, which `docker build` does not grant.
RUN cd /src/build && (ctest --output-on-failure -j"$(nproc)" --timeout 300 || echo "WARNING: ctest reported failures")
RUN cd /src/build-asan && (ASAN_OPTIONS=detect_leaks=0 ctest --output-on-failure -j"$(nproc)" --timeout 600 \
      || echo "WARNING: ASan ctest reported failures")
RUN mkdir -p /tmp/zxc-cli && cd /tmp/zxc-cli \
    && (ASAN_OPTIONS=detect_leaks=0 bash /src/tests/cli/test_cli.sh /src/build-asan/zxc \
        || echo "WARNING: CLI tests reported failures") \
    && rm -rf /tmp/zxc-cli
RUN for fuzzer in /src/build-fuzz/zxc_fuzzer_*; do \
      ASAN_OPTIONS=detect_leaks=0 "$fuzzer" -runs=0 /src/tests/conformance/v9/valid /src/tests/conformance/v9/invalid \
        >/dev/null 2>&1 || echo "WARNING: $fuzzer failed on the conformance vectors"; \
    done
