# Anthropic OSS Scanner enrollment for HOL Guard.
# This Dockerfile is evaluated with the hol-guard checkout as its build context.
# The image is built with network access; subsequent security analysis runs offline.
FROM rust:1.88-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_INCREMENTAL=0 \
    CARGO_BUILD_JOBS=4 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1 \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates clang cmake git libffi-dev \
      libssl-dev lld pkg-config python3 python3-dev python3-venv \
    && rm -rf /var/lib/apt/lists/*

# The checked-in Python lockfile is resolved with uv; Debian's Python 3.11
# satisfies the declared >=3.10 compatibility range.
RUN python3 -m venv /opt/uv-tools \
    && /opt/uv-tools/bin/pip install --no-cache-dir "uv>=0.9,<1"
ENV PATH="/opt/uv-tools/bin:${PATH}"

# Scanner contract: the project's checkout is available at /src.
COPY . /src
WORKDIR /src

# Include the developer test dependencies in the image for offline inspection.
# The editable Python installation does not rebuild the native Rust runtime.
RUN uv sync --frozen --python /usr/bin/python3 --no-default-groups --extra dev

# Fetch the locked Rust dependency graph while network access is available.
# Build HOL Guard's native runtime in addition to the Python CLI.
RUN cargo fetch --locked --manifest-path rust/Cargo.toml
RUN cargo build --locked --manifest-path rust/Cargo.toml \
      -p hol-guard-runtime --bin hol-guard-runtime \
    && install -m 0755 rust/target/debug/hol-guard-runtime \
      /usr/local/bin/hol-guard-runtime

# Python code and Rust sources, build artifacts and Cargo caches remain in
# the image. HOL Guard's own .dockerignore excludes the top-level tests/
# directory, but Rust unit tests and crate fixtures remain in rust/crates/.
RUN .venv/bin/python -c "import codex_plugin_scanner"
RUN cargo test --locked --manifest-path rust/Cargo.toml \
      -p guard-scanner --lib \
    || echo "WARNING: Rust library smoke tests reported failures"

# Prevent accidental dependency downloads during interactive offline analysis.
ENV CARGO_NET_OFFLINE=true \
    UV_OFFLINE=true \
    PATH="/src/.venv/bin:${PATH}"

CMD ["bash"]
