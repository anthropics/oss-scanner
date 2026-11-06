# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Adapted from google/oss-fuzz's projects/ots/Dockerfile and build.sh.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang libclang-rt-18-dev llvm gdb git \
      pkg-config python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Match OTS's current CI Meson version; keep the toolchain available offline.
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir meson==1.11.1 ninja

# The scanner supplies the OTS checkout as the build context.
COPY . /src
WORKDIR /src

# Use upstream's dependency wraps, as OSS-Fuzz does. This fetches and builds
# zlib, WOFF2, Brotli, LZ4, FreeType and GoogleTest before the offline audit.
# Keep the default Graphite, COLR cycle checks and gvar synthesis enabled.
RUN meson setup build --wrap-mode=forcefallback --buildtype=debugoptimized \
      --default-library=static -Db_ndebug=false \
      -Dc_args=-fno-omit-frame-pointer -Dcpp_args=-fno-omit-frame-pointer \
    && meson compile -C build -j "$(nproc)"

# Instrument OTS and its bundled dependencies with ASan, UBSan and coverage.
# fuzzer_ldflags selects the libFuzzer entry point in util/ots-fuzzer.cc.
RUN meson setup build-fuzz --wrap-mode=forcefallback --buildtype=debugoptimized \
      --default-library=static -Doptimization=1 -Db_ndebug=false \
      -Db_sanitize=address,undefined -Db_lundef=false \
      -Dc_args="-fno-omit-frame-pointer -fsanitize=fuzzer-no-link -fno-sanitize-recover=undefined" \
      -Dcpp_args="-fno-omit-frame-pointer -fsanitize=fuzzer-no-link -fno-sanitize-recover=undefined" \
      -Dfuzzer_ldflags=-fsanitize=fuzzer \
    && meson compile -C build-fuzz -j "$(nproc)"

ENV ASAN_OPTIONS=allocator_may_return_null=1:abort_on_error=1:detect_leaks=1:symbolize=1 \
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1

# OSS-Fuzz seeds ots-fuzzer with tests/fonts and uses max_len=1000000.
# Hash filenames to retain inputs with identical basenames in different suites.
RUN mkdir fuzzer_corpus \
    && find tests/fonts -type f -exec sh -ec \
      'for font do hash=$(sha256sum "$font"); cp "$font" "fuzzer_corpus/${hash%% *}"; done' sh {} + \
    && test -n "$(ls -A fuzzer_corpus)"

# Fail the build if the fuzzer cannot process a known-good font.
RUN build-fuzz/ots-fuzzer -runs=1 -max_len=1000000 \
      tests/fonts/good/00ae3c2b1b7718361fc76ee31da97253057b15b7.ttf

# Preserve binaries and test logs even if an upstream regression test fails.
RUN meson test -C build --print-errorlogs --num-processes 4 \
    || echo "WARNING: OTS tests reported failures; see build/meson-logs/testlog.txt"
# Match OSS-Fuzz's run_tests.sh for regression replay. Keep these two
# suppressions scoped to the test command, not the audit or mutation fuzzing.
RUN ASAN_OPTIONS="$ASAN_OPTIONS:detect_leaks=0:alloc_dealloc_mismatch=0" \
      meson test -C build-fuzz --print-errorlogs --num-processes 4 \
    || echo "WARNING: OTS sanitizer tests reported failures; see build-fuzz/meson-logs/testlog.txt"
