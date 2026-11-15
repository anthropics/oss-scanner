# OSS Scanner build for GNU FriBidi (https://github.com/fribidi/fribidi).
#
# FriBidi is a C implementation of the Unicode Bidirectional Algorithm. This builds two
# configurations:
#
#   /src/build       gcc, debugoptimized, static library, the `fribidi` CLI and the test binaries.
#   /src/build-asan  clang, ASan + UBSan, with the libFuzzer-linked fuzzer at
#                    /src/build-asan/bin/fribidi-fuzzer.
#
# The fuzzer and its flags follow google/oss-fuzz's projects/fribidi/build.sh.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang libclang-rt-18-dev lld llvm \
      meson ninja-build pkg-config python3 \
      gdb valgrind file xxd jq \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# 1) Reference build: library, CLI, and the full upstream test suite.
RUN CC=gcc meson setup /src/build /src \
      --buildtype=debugoptimized \
      --default-library=static \
      --wrap-mode=nodownload \
      -Ddocs=false \
      -Ddeprecated=true \
      -Dbin=true \
      -Dtests=true \
      -Dc_args="-g -fno-omit-frame-pointer" \
    && meson compile -C /src/build -j "$(nproc)"

# 2) Sanitizer build with the libFuzzer target. -fsanitize=fuzzer-no-link instruments coverage
#    at compile time; fuzzer_ldflags links the libFuzzer main at link time.
RUN CC=clang meson setup /src/build-asan /src \
      --buildtype=debugoptimized \
      --default-library=static \
      --wrap-mode=nodownload \
      -Ddocs=false \
      -Ddeprecated=true \
      -Dbin=true \
      -Dtests=true \
      -Db_sanitize=address,undefined \
      -Db_lundef=false \
      -Dfuzzer_ldflags="-fsanitize=fuzzer" \
      -Dc_args="-g -O1 -fno-omit-frame-pointer -fno-sanitize-recover=undefined -fsanitize=fuzzer-no-link" \
    && meson compile -C /src/build-asan -j "$(nproc)"

ENV ASAN_OPTIONS=abort_on_error=1:detect_leaks=1:symbolize=1 \
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1

# Seed corpus: the same files oss-fuzz zips for fribidi-fuzzer.
RUN set -e; mkdir -p /src/fuzzer_corpus \
    && cp -a test/*.input test/*.reference test/fuzzing/. /src/fuzzer_corpus/

# Smoke tests. The ASan build also runs the two test/fuzzing regression inputs through the
# libFuzzer target, because meson registers them as tests when fuzzer_ldflags is set.
# Failures are reported but never abort the image build.
RUN cd /src/build \
    && (timeout 20m meson test --no-rebuild --print-errorlogs --timeout-multiplier 10 \
        || echo "WARNING: fribidi tests reported failures or ran out of time")

RUN cd /src/build-asan \
    && (ASAN_OPTIONS=abort_on_error=1:detect_leaks=0:symbolize=1 \
          timeout 20m meson test --no-rebuild --print-errorlogs --timeout-multiplier 10 \
        || echo "WARNING: fribidi ASan tests reported failures or ran out of time")

# One input through the libFuzzer target, to show that it starts and links.
RUN set -e; seed=$(find /src/fuzzer_corpus -type f | head -n 1); \
    ASAN_OPTIONS=abort_on_error=1:detect_leaks=0:symbolize=1 \
      timeout 2m /src/build-asan/bin/fribidi-fuzzer -runs=1 "$seed" >/dev/null 2>&1 \
      || echo "WARNING: fribidi-fuzzer failed its smoke run"
