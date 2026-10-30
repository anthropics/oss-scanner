# syntax=docker/dockerfile:1
# Trixie supports the ARM64 wheel for Foundry's pinned Z3 version.
FROM rust:1.98-trixie

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang lld cmake pkg-config libssl-dev \
      curl perl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Match the Vyper and symbolic solver versions used by Foundry's CI.
RUN python3 -m venv /opt/foundry-tools \
    && /opt/foundry-tools/bin/pip install --no-cache-dir vyper==0.4.3 z3-solver==5.1.0.0

# Cache Solidity's release manifest and the compiler used by Foundry's test fixtures.
# SVM reads this manifest during Rust compilation, including offline rebuilds.
RUN python3 - <<'PY'
import hashlib
import json
import platform
from pathlib import Path
from urllib.request import urlopen

arch = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
base = f"https://raw.githubusercontent.com/ethereum/solc-bin/gh-pages/linux-{arch}"
with urlopen(f"{base}/list.json") as response:
    manifest = json.load(response)
manifest["builds"] = [
    build for build in manifest["builds"]
    if manifest["releases"].get(build["version"]) == build["path"]
]
Path("/opt/solc").mkdir()
Path("/opt/solc/list.json").write_text(json.dumps(manifest))
version = "0.8.38"
artifact = manifest["releases"][version]
build = next(build for build in manifest["builds"] if build["path"] == artifact)
with urlopen(f"{base}/{artifact}") as response:
    binary = response.read()
assert hashlib.sha256(binary).hexdigest() == build["sha256"].removeprefix("0x")
compiler = Path(f"/root/.svm/{version}/solc-{version}")
compiler.parent.mkdir(parents=True)
compiler.write_bytes(binary)
compiler.chmod(0o755)
Path("/usr/local/bin/solc").symlink_to(compiler)
PY

# Retain source and dependencies for offline analysis and patch testing.
COPY . /src
WORKDIR /src
RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true \
    CARGO_BUILD_JOBS=4 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    CARGO_PROFILE_RELEASE_STRIP=none \
    CARGO_PROFILE_RELEASE_LTO=false \
    RUSTFLAGS="-C force-frame-pointers=yes -C link-arg=-fuse-ld=lld" \
    CFLAGS="-g1 -fno-omit-frame-pointer" \
    CXXFLAGS="-g1 -fno-omit-frame-pointer" \
    SVM_RELEASES_LIST_JSON=/opt/solc/list.json \
    PATH="/src/target/release:/opt/foundry-tools/bin:${PATH}"

# Build the CLI tools with their default features, debug information and frame pointers.
RUN cargo build --locked --release --bins -p forge -p cast -p anvil -p chisel -p solar

# Precompile self-contained tests for parsing, formatting and Anvil's core types.
RUN cargo test --locked --release --lib --no-run \
      -p foundry-primitives -p forge-fmt -p anvil-core
