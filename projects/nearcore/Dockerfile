# syntax=docker/dockerfile:1
FROM rust:1.95-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_BUILD_JOBS=2 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_ARTIFACTS_DEBUG=1 \
    RUST_TEST_THREADS=2 \
    RUST_BACKTRACE=1 \
    PORTABLE=ON \
    CXX=clang++ \
    CXXFLAGS=-gline-tables-only \
    INSTA_UPDATE=no \
    CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=clang-lld \
    CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=clang-lld

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang llvm libclang-dev lld cmake pkg-config libssl-dev \
      libudev-dev protobuf-compiler binutils-dev libunwind-dev \
      libcurl4-openssl-dev zlib1g-dev libdw-dev libiberty-dev \
      python3 python3-venv curl ca-certificates jq \
    && rm -rf /var/lib/apt/lists/* \
    && rustup component add rustfmt clippy rust-analyzer rust-src \
    && rustup target add wasm32-unknown-unknown

# lld keeps node/test linking within the scanner's memory budget. Selecting a
# linker preserves the checked-in architecture flags and unwind-table settings.
# Explicitly link libstdc++ even when librocksdb-sys reuses an existing archive
# and therefore does not emit cc-rs's usual C++ runtime link directive.
RUN printf '#!/bin/sh\nexec clang -fuse-ld=lld "$@" -lstdc++\n' > /usr/local/bin/clang-lld \
    && chmod +x /usr/local/bin/clang-lld

COPY --exclude=.oss-scanner . /work/nearcore
RUN ln -s /work/nearcore /src
WORKDIR /work/nearcore

# Include the Python harness dependencies, all locked Rust dependencies, and the
# nested Wasm workspaces built by near-test-contracts during native tests.
RUN python3 -m venv /opt/nearcore-venv \
    && /opt/nearcore-venv/bin/pip install -r pytest/requirements.txt \
    && cargo fetch --locked \
    && find runtime/near-test-contracts -mindepth 2 -name Cargo.toml \
      -exec sh -ec 'for manifest do cargo fetch --locked --manifest-path "$manifest"; done' sh '{}' +
ENV PATH="/opt/nearcore-venv/bin:${PATH}"

# Build the default-feature node first. Cargo's node/test build graphs select
# different build-dependency features and otherwise compile identical RocksDB
# sources twice. Reuse the first build's static archives through librocksdb-sys's
# supported environment variables, rather than a different system RocksDB.
# Keep both builds in one layer, retaining archives but removing native .o files
# after linking. Rust and C++ retain line-table debug info for investigations.
ENV ROCKSDB_STATIC=1 SNAPPY_STATIC=1
RUN <<'SH'
set -eu
jobs=$(nproc)
if [ "$jobs" -gt 8 ]; then jobs=8; fi
cargo build --locked --profile dev-artifacts -p neard -j "$jobs"
mkdir /opt/nearcore-native
for library in rocksdb snappy; do
    archive=$(find target/dev-artifacts/build -path "*/librocksdb-sys-*/out/lib${library}.a")
    test -n "$archive"
    test "$(printf '%s\n' "$archive" | wc -l)" -eq 1
    cp "$archive" /opt/nearcore-native/
done
export ROCKSDB_LIB_DIR=/opt/nearcore-native SNAPPY_LIB_DIR=/opt/nearcore-native
cargo test --locked --profile dev-artifacts --features test_features \
    -p near-network -p near-vm-runner -p near-runtime -p test-loop-tests \
    --lib --no-run -j "$jobs"
# Refresh the default node's Cargo fingerprints for the same native-lib settings
# used by future offline builds. This does not enable the tests' feature graph.
cargo build --locked --profile dev-artifacts -p neard -j "$jobs"
ln -s /work/nearcore/target/dev-artifacts/neard /usr/local/bin/neard
find target/dev-artifacts/build -path '*/librocksdb-sys-*/out/*' -name '*.o' -delete
SH
ENV ROCKSDB_LIB_DIR=/opt/nearcore-native SNAPPY_LIB_DIR=/opt/nearcore-native
RUN curl -fsSL \
      "https://github.com/nextest-rs/nextest/releases/download/cargo-nextest-0.9.150/cargo-nextest-0.9.150-$(uname -m)-unknown-linux-gnu.tar.gz" \
      -o /tmp/nextest.tar.gz \
    && tar -xzf /tmp/nextest.tar.gz -C /usr/local/cargo/bin cargo-nextest \
    && rm /tmp/nextest.tar.gz \
    && cargo nextest --version

RUN <<'SH'
cat > /usr/local/bin/nearcore-tests <<'SCRIPT'
#!/bin/sh
set -eu
cd /src
# Use the repository's fast-test profile and process-per-test isolation. The
# excluded test queries public STUN servers; local STUN/network tests run.
# Include the four basic TestLoop scenarios without running its full CI matrix.
cargo nextest run --locked --cargo-profile dev-artifacts --features test_features \
  -p near-network -p near-vm-runner -p near-runtime -p test-loop-tests --lib \
  --profile default --test-threads 2 \
  -E '(not package(test-loop-tests) & not test(stun::tests::test_lookup_host)) | (package(test-loop-tests) & test(/^examples::basic::/))'
SCRIPT
chmod +x /usr/local/bin/nearcore-tests

cat > /usr/local/bin/nearcore-local-smoke <<'SCRIPT'
#!/usr/bin/env python3
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

with tempfile.TemporaryDirectory(prefix="nearcore-local-") as temporary:
    root = Path(temporary)
    subprocess.run([
        "neard", "--home", str(root), "localnet",
        "--validators", "1", "--shards", "1",
    ], check=True)
    home = root / "node0"
    config_path = home / "config.json"
    config = json.loads(config_path.read_text())
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config["rpc"]["addr"] = f"127.0.0.1:{port}"
    config["telemetry"]["endpoints"] = []
    config_path.write_text(json.dumps(config))
    with (root / "node.log").open("w+") as log:
        process = subprocess.Popen(
            ["neard", "--home", str(home), "run"],
            stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"node exited with {process.returncode}")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/status", timeout=2,
                    ) as response:
                        status = json.load(response)
                    height = status["sync_info"]["latest_block_height"]
                    if height >= 3:
                        print(f"local node produced blocks through height {height}")
                        break
                except (OSError, urllib.error.URLError, KeyError):
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("local node did not produce three blocks")
        except BaseException:
            log.flush()
            log.seek(0)
            print(log.read()[-16000:])
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
SCRIPT
chmod +x /usr/local/bin/nearcore-local-smoke
SH

# Test harnesses and contracts are prebuilt above. The baseline commands are
# verified separately in the finished image with networking disabled.
RUN neard --version

ENV CARGO_NET_OFFLINE=true
