# Scanner image for https://github.com/safetensors/safetensors.
#
# The audit runs offline, so this build fetches every crate and Python package, builds the Rust crate, its tests and
# fuzz target, and installs the Python bindings into /opt/venv with CPU-only PyTorch. threat_model.md says how to
# run each of them.

# Stable Rust, as CI uses. The crate's MSRV is 1.86.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends clang python3 python3-dev \
    && rm -rf /var/lib/apt/lists/*

# cargo-fuzz needs nightly for its sanitizer flags.
RUN rustup toolchain install nightly --profile minimal \
    && cargo install cargo-fuzz --locked

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

# The Python environment the tests use. torch comes from the CPU index; the image has no GPU.
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    UV_LINK_MODE=copy
RUN uv venv --python /usr/bin/python3 /opt/venv \
    && uv pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && uv pip install numpy h5py pytest pytest-benchmark "maturin>=1.0,<2.0"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8
# Release builds keep debug info so backtraces and debuggers are useful.
ENV CARGO_PROFILE_RELEASE_DEBUG=true \
    RUST_BACKTRACE=1

# Every crate for the core crate, the bindings and the fuzz target.
RUN cd /src/safetensors && cargo fetch --locked \
    && cd /src/bindings/python && cargo fetch --locked

# The core crate and its tests, the fuzz target (ASan, nightly), and the Python extension installed into /opt/venv. A
# step that fails fails the build, and primary_contact gets the log.
RUN cd /src/safetensors && cargo build --locked --all-targets && cargo test --locked --no-run \
    && cargo +nightly fuzz build fuzz_target_1 \
    && cd /src/bindings/python && cargo test --locked --no-run \
    && maturin develop --release --uv

# Run the tests so the log shows the image works, without letting a failure abort the build. The TensorFlow, Flax,
# Paddle and MLX comparison tests need frameworks this image does not install.
RUN (cd /src/safetensors && timeout 1200 cargo test --locked || echo "WARNING: cargo test (safetensors) reported failures") \
    && (cd /src/bindings/python && timeout 1200 cargo test --locked || echo "WARNING: cargo test (bindings) reported failures") \
    && (cd /src/bindings/python && timeout 1200 pytest -q tests/ \
          --ignore=tests/test_tf_comparison.py --ignore=tests/test_flax_comparison.py \
          --ignore=tests/test_paddle_comparison.py --ignore=tests/test_mlx_comparison.py \
        || echo "WARNING: pytest reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
