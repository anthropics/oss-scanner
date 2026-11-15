# The scanner supplies a Fontations checkout as the build context. Fetch all
# dependencies and test data before the offline audit, including build-script
# downloads that Cargo itself does not cache.
FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    CARGO_BUILD_JOBS=4 \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    CFLAGS="-g -fno-omit-frame-pointer" \
    CXXFLAGS="-g -fno-omit-frame-pointer" \
    CARGO_PROFILE_RELEASE_DEBUG=2 \
    CARGO_PROFILE_RELEASE_LTO=false \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang cmake gdb git pkg-config \
      libfreetype6-dev python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN rustup toolchain install nightly --profile minimal --component rust-src \
    && cargo install cargo-fuzz --locked

# The shared-brotli-patch-decoder build script clones Brotli into OUT_DIR for
# each build configuration. Redirect those clones to a full local mirror so
# new targets, feature combinations and sanitizer builds also work offline.
RUN git clone --mirror https://github.com/google/brotli.git /opt/brotli.git \
    && git config --system url."file:///opt/brotli.git".insteadOf \
      https://github.com/google/brotli.git

COPY . /src
WORKDIR /src

# Cargo.lock is not tracked upstream; generate it once and retain the lockfile
# and registry cache for repeatable, offline rebuilds of this checkout.
RUN cargo fetch \
    && python3 -m venv /opt/venv \
    && pip install --no-cache-dir -r resources/scripts/skera_ci_requirements.txt

ENV CARGO_NET_OFFLINE=true

# Build the libraries and CLI tools with debug information. Keep
# debug test binaries as well as optimized tools for reproduction.
RUN cargo build --locked --release --workspace --exclude fuzz --all-features \
    && cargo test --locked --workspace --exclude fuzz \
    && cargo test --locked --workspace --exclude fuzz --all-features \
    && cargo test --locked -p write-fonts --no-default-features --tests \
    && cargo test --locked -p shared-brotli-patch-decoder --no-default-features \
      --features rust-brotli \
    && cargo test --locked -p incremental-font-transfer --no-default-features \
      --features rust-brotli

# Match the upstream OSS-Fuzz build: optimized libFuzzer engines, ASan and
# debug assertions. Instrument the C Brotli decoder too.
RUN CFLAGS="${CFLAGS} -fsanitize=address" \
    CXXFLAGS="${CXXFLAGS} -fsanitize=address" \
    cargo +nightly fuzz build -O --debug-assertions

ENV ASAN_OPTIONS=allocator_may_return_null=1:abort_on_error=1:detect_leaks=1:symbolize=1 \
    RUST_BACKTRACE=1

# Use the same external font sources as Fontations' OSS-Fuzz configuration,
# plus this checkout's regression fixtures. Keep distinct equal-basename files.
RUN git clone --depth 1 https://github.com/unicode-org/text-rendering-tests.git /opt/font-corpora/text-rendering-tests \
    && git clone --depth 1 https://github.com/googlefonts/color-fonts.git /opt/font-corpora/color-fonts \
    && git clone --depth 1 https://github.com/harfbuzz/harfbuzz.git /opt/font-corpora/harfbuzz

RUN python3 - <<'PY'
import hashlib
from pathlib import Path
import subprocess
import tomllib

corpus = Path('/src/fuzzer_corpus/fonts')
corpus.mkdir(parents=True)
for directory in [
    'font-test-data/test_data', 'fauntlet/test_fonts', 'skera/test-data',
    'incremental-font-transfer/resources/testdata',
    '/opt/font-corpora/text-rendering-tests/fonts',
    '/opt/font-corpora/color-fonts/fonts', '/opt/font-corpora/harfbuzz/test',
]:
    for source in sorted(Path(directory).rglob('*')):
        if source.is_file() and source.suffix.lower() in {'.ttf', '.otf', '.ttc', '.otc'}:
            data = source.read_bytes()
            (corpus / hashlib.sha256(data).hexdigest()).write_bytes(data)
assert any(corpus.iterdir()), 'No font seeds collected'

smoke = Path('/tmp/fontations-fuzz-smoke')
smoke.mkdir()
sample = smoke / 'operations'
sample.write_bytes(bytes(32))
font = Path('font-test-data/test_data/ttf/simple_closure.ttf')
manifest = tomllib.loads(Path('fuzz/Cargo.toml').read_text())
targets = [target['name'] for target in manifest['bin']]
assert targets, 'No fuzz targets found'
font_targets = {
    'fuzz_basic_metadata', 'fuzz_name', 'fuzz_skrifa_charmap',
    'fuzz_skrifa_outline', 'fuzz_skrifa_color',
}
for target in targets:
    seed = font if target in font_targets else sample
    print(f'Smoke test: {target}', flush=True)
    subprocess.run([
        f'target/x86_64-unknown-linux-gnu/release/{target}',
        '-runs=1', '-timeout=20', '-rss_limit_mb=2048',
        f'-artifact_prefix={smoke}/', str(seed),
    ], check=True, timeout=60)
PY
