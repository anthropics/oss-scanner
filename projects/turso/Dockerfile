# OSS Scanner build for Turso Database (https://github.com/tursodatabase/turso).
#
# The scanner builds this with the turso checkout as the build context, with network access, and then
# runs its audit against the finished image with NO network. Everything the build or the tests need is
# fetched here: the Rust toolchain and its components, every crate in Cargo.lock (dev-dependencies
# included), cargo-nextest, uv and the Python test runner's dependencies.
#
# The build follows turso's own Linux CI (.github/workflows/rust.yml): a debug build of the default
# workspace members with --all-features, then every test binary of the workspace, so that
# `cargo nextest run` / `cargo test` work offline afterwards.

# No Rust in the base image: rust-toolchain.toml pins channel `1.88`, which rustup treats as a different
# toolchain from the `1.88.0` that rust:* images ship, so those would carry two copies of the same compiler.
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/root/.local/bin:$PATH

# clang/libclang: bindgen (pg_query in postgres/parser, sdk-kit). protobuf-compiler: prost build scripts.
# libsqlite3-dev + sqlite3: differential tests against SQLite. python3-dev: PyO3 (bindings/python).
# tcl: the SQLite-style compatibility suite in testing/system (`make test-compat`).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential clang libclang-dev llvm pkg-config cmake \
      protobuf-compiler libssl-dev libsqlite3-dev sqlite3 python3 python3-dev python3-pip tcl \
    && rm -rf /var/lib/apt/lists/*

# rustup alone; the toolchain comes from rust-toolchain.toml below.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain none

# rust-toolchain.toml pins the channel and asks for clippy, rustfmt and rust-analyzer. Install exactly what
# it says now, while the network is up: rustup would otherwise fetch them the first time cargo runs. Only
# that file is copied for this, so the toolchain layer survives changes to the rest of the checkout.
COPY rust-toolchain.toml /src/rust-toolchain.toml
WORKDIR /src
RUN rustup toolchain install && rustup show active-toolchain && rustup toolchain list

# cargo-nextest is what CI uses to run the test suite. Prebuilt binary; falls back to cargo install.
RUN set -e; \
    case "$(uname -m)" in \
      x86_64)  flavour=linux ;; \
      aarch64) flavour=linux-arm ;; \
      *)       flavour= ;; \
    esac; \
    if [ -n "$flavour" ] && curl -fsSL "https://get.nexte.st/latest/$flavour" | tar zxf - -C /usr/local/cargo/bin; then \
      cargo nextest --version; \
    else \
      cargo install cargo-nextest --locked; \
    fi

# uv drives the Python test runner (testing/, `make test-shell` etc.) and the Python bindings.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# scanner contract: the checkout lives inside the image, at /src
COPY . /src

# No RUSTFLAGS here: setting it replaces the rustflags in turso's .cargo/config.toml (--cfg=tokio_unstable, which
# sync/engine needs, and the Linux link args the napi test binaries need) instead of adding to them.
ENV PYO3_PYTHON=/usr/bin/python3 \
    LOCAL_SYNC_SERVER=../../target/debug/tursodb

# Everything in Cargo.lock, including dev-dependencies, so that any later cargo invocation can run offline.
RUN cargo fetch --locked

# 1. The build CI does: default workspace members with every feature enabled.
RUN cargo build --locked --all-features

# 2. Every test binary in the workspace (what `cargo nextest run --workspace --all-features` would run),
#    excluding the benchmark crate, so tests can be run offline without a compile step.
RUN cargo test --no-run --locked --workspace --all-features --exclude memory-benchmark

# 3. The Python test runner's environment and the managed interpreter it wants (.python-version).
RUN (uv sync --all-extras --dev --package turso_test || echo "WARNING: uv sync failed; Python test runner unavailable")

# Smoke test while the --all-features build from steps 1-2 is current: reports but never aborts.
RUN (timeout 900 cargo nextest run --locked --no-fail-fast --all-features -p turso_core \
       --failure-output=final || echo "WARNING: turso_core unit tests reported failures")

# 4. Leave target/debug as the plain `cargo build` that the Makefile and the Python and TCL suites expect.
#    The --all-features tursodb has page checksums on (`.dbtotxt` output differs) and turso_ext_tests built
#    `static` (no register_extension), so `make test-compat` and `test-shell` fail against it. Switching
#    feature sets later rebuilds about 30 crates offline: 30-90 seconds, nothing fetched.
RUN cargo build --locked
RUN ./target/debug/tursodb --version

# The audit runs with no network: tell cargo and uv up front so nothing waits on a socket.
ENV CARGO_NET_OFFLINE=true \
    UV_OFFLINE=1
