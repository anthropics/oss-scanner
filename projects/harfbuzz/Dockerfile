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
################################################################################

# The scanner supplies a HarfBuzz checkout as the build context. Everything
# needed to rebuild or run tests must be present before the offline audit.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang libclang-rt-18-dev llvm gdb git \
      pkg-config python3-venv ragel \
      libcairo2-dev libfreetype6-dev libglib2.0-dev libgraphite2-dev \
      libicu-dev libpng-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Use the same Meson, Ninja and FontTools versions as upstream CI. The virtual
# environment and installed packages remain available without network access.
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir --require-hashes -r .ci/requirements.txt

# Normal build, with debug information, assertions and frame pointers. Keep
# libraries in the build tree so the tools use this checkout's HarfBuzz.
RUN meson setup build --wrap-mode=nofallback --buildtype=debugoptimized \
      -Db_ndebug=false \
      -Dc_args=-fno-omit-frame-pointer -Dcpp_args=-fno-omit-frame-pointer \
      -Dglib=enabled -Dgobject=enabled -Dfreetype=enabled -Dcairo=enabled \
      -Dicu=enabled -Dgraphite2=enabled -Dpng=enabled -Dzlib=enabled \
      -Dsubset=enabled -Draster=enabled -Dvector=enabled -Dgpu=enabled \
      -Dgpu_demo=disabled -Dtests=enabled -Dutilities=enabled \
      -Ddocs=disabled -Dintrospection=disabled \
    && meson compile -C build -j "$(nproc)"

# A second tree instruments the libraries, command-line tools and standalone
# fuzz drivers, and includes experimental APIs such as dependency analysis.
RUN meson setup build-asan --wrap-mode=nofallback --buildtype=debugoptimized \
      -Db_ndebug=false -Db_sanitize=address,undefined -Db_lundef=false \
      -Dc_args=-fno-omit-frame-pointer -Dcpp_args=-fno-omit-frame-pointer \
      -Dglib=enabled -Dgobject=enabled -Dfreetype=enabled -Dcairo=enabled \
      -Dicu=enabled -Dgraphite2=enabled -Dpng=enabled -Dzlib=enabled \
      -Dsubset=enabled -Draster=enabled -Dvector=enabled -Dgpu=enabled \
      -Dgpu_demo=disabled -Dtests=enabled -Dutilities=enabled \
      -Ddocs=disabled -Dintrospection=disabled -Dexperimental_api=true \
    && meson compile -C build-asan -j "$(nproc)"

ENV ASAN_OPTIONS=allocator_may_return_null=1:abort_on_error=1:detect_leaks=1:symbolize=1 \
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1

# Keep mutation fuzzing separate from the TAP replay drivers. Setting
# fuzzer_ldflags also enables HarfBuzz's custom failing allocator, as in OSS-Fuzz.
# Only build the security fuzzers; Meson's tests run in the two trees above.
RUN meson setup build-fuzz --wrap-mode=nofallback --buildtype=debugoptimized \
      --default-library=static -Doptimization=1 \
      -Db_ndebug=false -Db_sanitize=address,undefined -Db_lundef=false \
      -Dc_args="-fno-omit-frame-pointer -fsanitize=fuzzer-no-link -fno-sanitize=vptr -fno-sanitize-recover=undefined -DHB_NO_VISIBILITY" \
      -Dcpp_args="-fno-omit-frame-pointer -fsanitize=fuzzer-no-link -fno-sanitize=vptr -fno-sanitize-recover=undefined -DHB_NO_VISIBILITY" \
      -Dfuzzer_ldflags=-fsanitize=fuzzer \
      -Dglib=enabled -Dgobject=enabled -Dfreetype=enabled -Dcairo=enabled \
      -Dicu=enabled -Dgraphite2=enabled -Dpng=enabled -Dzlib=enabled \
      -Dsubset=enabled -Draster=enabled -Dvector=enabled -Dgpu=enabled \
      -Dgpu_demo=disabled -Dtests=enabled -Dutilities=disabled \
      -Ddocs=disabled -Dintrospection=disabled -Dexperimental_api=true \
    && meson compile -C build-fuzz -j "$(nproc)" \
      hb-shape-fuzzer hb-subset-fuzzer hb-raster-fuzzer hb-vector-fuzzer \
      hb-gpu-fuzzer hb-repacker-fuzzer hb-depend-fuzzer

# Combine upstream's font/graph seeds without overwriting equal basenames.
# Names are content hashes, so identical inputs are deduplicated as well.
RUN python3 - <<'PY'
import hashlib
from pathlib import Path

def collect(sources, output):
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    for directory in sources:
        for source in sorted(Path(directory).rglob('*')):
            if source.is_file():
                data = source.read_bytes()
                (destination / hashlib.sha256(data).hexdigest()).write_bytes(data)
    assert any(destination.iterdir()), output

collect([
    'test/shape/data/in-house/fonts',
    'test/shape/data/aots/fonts',
    'test/shape/data/text-rendering-tests/fonts',
    'test/api/fonts', 'test/fuzzing/fonts', 'test/subset/data/fonts', 'perf/fonts',
], 'fuzzer_corpus/fonts')
collect(['test/fuzzing/graphs'], 'fuzzer_corpus/graphs')
PY

# Exercise each libFuzzer entry point with a small valid seed, both with and
# without allocation-failure injection. Appending a byte preserves font/graph
# parsing while selecting the allocator mode via _fuzzing_alloc_state().
RUN python3 - <<'PY'
from pathlib import Path
import subprocess

directory = Path('/tmp/hb-fuzz-smoke')
directory.mkdir(exist_ok=True)
font = Path('test/api/fonts/Roboto-Regular.abc.ttf')
graph = min(Path('test/fuzzing/graphs').iterdir(), key=lambda p: (p.stat().st_size, p.name))
for target in ['shape', 'subset', 'raster', 'vector', 'gpu', 'repacker', 'depend']:
    seed = graph if target == 'repacker' else font
    for mode, marker in [('normal', 0), ('oom', 128)]:
        sample = directory / f'{target}-{mode}'
        sample.write_bytes(seed.read_bytes() + bytes([marker]))
        print(f'Smoke test: hb-{target}-fuzzer ({mode})', flush=True)
        subprocess.run([
            f'build-fuzz/test/fuzzing/hb-{target}-fuzzer',
            '-runs=1', '-timeout=10', '-rss_limit_mb=2048',
            f'-artifact_prefix={directory}/', str(sample),
        ], check=True, timeout=30)
PY

# Preserve test logs and binaries for the audit even if an upstream test fails.
RUN meson test -C build --print-errorlogs --num-processes 4 \
    || echo "WARNING: HarfBuzz tests reported failures; see build/meson-logs/testlog.txt"
