# SGLang-Omni: Python serving framework (sglang_omni/), Python and Rust request routers (sglang_omni_router/),
# native C++ MLX servers (sglang_omni_mlx/native), playgrounds, and the Voxt macOS app (source only).
# CPU-only image. The core install matches the project's own docker/cpu.Dockerfile, which the per-PR CPU CI job
# builds. On top of it the image builds the Rust router with its tests, adds playground dependencies, the inputs
# needed to compile the native C++ parsers on Linux, and offline audit tools. Only the core steps can fail the build.
ARG SGLANG_IMAGE=lmsysorg/sglang:v0.5.21-xeon@sha256:6d4416ce9f9b607dcc74f1df1eb7b592c636c2654373053c6ff7c8dc6396552c
FROM ${SGLANG_IMAGE}
SHELL ["/bin/bash", "-c"]

# torchcodec loads FFmpeg's shared libraries at import time, so FFmpeg and libsndfile are runtime dependencies.
# cmake, ninja, and clang are for compiling native harnesses with sanitizers.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
      ca-certificates curl git xz-utils build-essential pkg-config clang cmake ninja-build ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/.venv \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup
ENV PATH="/usr/local/cargo/bin:/opt/.venv/bin:${PATH}"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Python package (core, fails the build). The base image's uv config prefers the PyTorch CPU index, so build tooling
# and test tools come from PyPI explicitly, as in docker/cpu.Dockerfile and the CPU CI job. uv reads the CPU
# dependency set only under the name pyproject.toml, so pyproject_cpu.toml is copied for that. It is swapped in for
# the editable install and the original pyproject.toml is put back, so the checkout under /src stays unmodified.
RUN uv pip install --upgrade --index https://pypi.org/simple "packaging>=24.2" "setuptools>=77.0.0" \
    && mkdir -p /tmp/cpu-deps \
    && cp /src/pyproject_cpu.toml /tmp/cpu-deps/pyproject.toml \
    && uv pip install --no-build-isolation -r /tmp/cpu-deps/pyproject.toml \
    && rm -r /tmp/cpu-deps \
    && uv pip install --index https://pypi.org/simple \
      "pytest>=7.0.0" "pytest-asyncio>=0.21.0" pytest-timeout httpx "hypothesis==6.168.3" \
    && cp /src/pyproject.toml /tmp/pyproject.orig.toml \
    && cp /src/pyproject_cpu.toml /src/pyproject.toml \
    && uv pip install --no-deps --no-build-isolation -e /src \
    && cp /tmp/pyproject.orig.toml /src/pyproject.toml \
    && rm /tmp/pyproject.orig.toml \
    && python -c "import sglang_omni, sglang_omni_router.python, sglang_omni.serve.openai_api"

# Playground dependencies (gradio, aiohttp), held to the versions already installed so they cannot change the core
# environment. If they do not fit, the playgrounds stay source-only.
RUN uv pip freeze --exclude-editable > /tmp/core-constraints.txt \
    && (uv pip install --index https://pypi.org/simple -c /tmp/core-constraints.txt "gradio>=4.0.0" aiohttp \
      || echo "WARNING: playground dependencies not installed") \
    && rm /tmp/core-constraints.txt

# Rust router (core, fails the build), with the toolchain pinned in sglang_omni_router/rust/rust-toolchain.toml.
# Test binaries are built too, so cargo test works without the network.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none \
    && cd /src/sglang_omni_router/rust \
    && rustup toolchain install \
    && cargo fetch --locked \
    && cargo build --workspace --all-targets --all-features --locked \
    && cargo test --workspace --all-targets --all-features --locked --no-run

# Native MLX servers. The full build needs macOS (CoreFoundation), so this provides what compiling the shared
# parsers and handlers into sanitizer harnesses on Linux needs: a Linux CPU build of the pinned MLX, and the
# CivetWeb, PCRE2, and nlohmann_json sources at the commits sglang_omni_mlx/native/CMakeLists.txt pins.
RUN (uv venv /opt/mlx-venv \
      && uv pip install --python /opt/mlx-venv/bin/python --index https://pypi.org/simple "mlx[cpu]==0.32.3" \
      || echo "WARNING: Linux MLX not installed") \
    && mkdir -p /opt/mlx-native-deps \
    && (git init -q /opt/mlx-native-deps/civetweb \
      && git -C /opt/mlx-native-deps/civetweb fetch -q --depth 1 https://github.com/civetweb/civetweb.git \
        d7ba35bbb649209c66e582d5a0244ba988a15159 \
      && git -C /opt/mlx-native-deps/civetweb checkout -q FETCH_HEAD \
      || echo "WARNING: CivetWeb source not fetched") \
    && (git init -q /opt/mlx-native-deps/pcre2 \
      && git -C /opt/mlx-native-deps/pcre2 fetch -q --depth 1 https://github.com/PCRE2Project/pcre2.git \
        6ae58beca071f13ccfed31d03b3f479ab520639b \
      && git -C /opt/mlx-native-deps/pcre2 checkout -q FETCH_HEAD \
      || echo "WARNING: PCRE2 source not fetched") \
    && (curl -fsSL -o /opt/mlx-native-deps/json.tar.xz \
        https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz \
      && echo "d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d  /opt/mlx-native-deps/json.tar.xz" \
        | sha256sum -c - \
      && tar -xJf /opt/mlx-native-deps/json.tar.xz -C /opt/mlx-native-deps \
      && rm /opt/mlx-native-deps/json.tar.xz \
      || echo "WARNING: nlohmann_json source not fetched")

# Offline audit tools, kept out of the project environment: bandit for Python, zizmor for GitHub Actions,
# cargo-audit with a snapshot of the RustSec advisory database, and a list of every installed Python package.
RUN (uv venv /opt/audit-tools \
      && uv pip install --python /opt/audit-tools/bin/python --index https://pypi.org/simple \
        "bandit==1.9.4" "zizmor==1.30.1" \
      || echo "WARNING: bandit and zizmor not installed") \
    && (cd /src/sglang_omni_router/rust && cargo install --locked cargo-audit@0.22.2 \
      || echo "WARNING: cargo-audit not installed") \
    && (git clone -q --depth 1 https://github.com/rustsec/advisory-db.git /opt/rustsec-advisory-db \
      || echo "WARNING: RustSec advisory database not fetched") \
    && mkdir -p /opt/audit \
    && uv pip freeze > /opt/audit/python-freeze.txt

# The scan runs without the network, so make Hugging Face lookups fail fast instead of waiting on timeouts.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# Cheap smoke runs so the image is known to work. Failures do not abort the build.
RUN (python -m pytest tests/unit_test/cpu -q -p no:cacheprovider || echo "WARNING: CPU unit tests reported failures") \
    && (python -m pytest --collect-only -q -p no:cacheprovider \
        tests/unit_test/serve tests/unit_test/router tests/unit_test/preprocessing > /dev/null \
      || echo "WARNING: some serve, router, or preprocessing tests fail to import") \
    && (cd /src/sglang_omni_router/rust && cargo test --workspace --all-features --locked -- --test-threads=1 \
      || echo "WARNING: Rust router tests reported failures")
