# OSS Scanner image for BasedHardware/omi, scoped to the Python backend.
#
# Production images (backend/Dockerfile, backend/Dockerfile.desktop_backend) use a
# private base `gcr.io/based-hardware-dev/python:3.11-slim-forky` and `uv pip sync`
# of backend/pylock.runtime.toml. This file follows that install path with a public
# Python 3.11 slim image so the scanner can pull it, and syncs backend/pylock.toml
# (runtime + unit/e2e test extras: pytest, fake-firestore, fakeredis) so an offline
# agent can read and run backend tests.
#
# Scanner contract: the omi checkout is the build context. COPY . /src. Network is
# available during this build and removed afterwards — fetch everything here.

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    UV_VERSION=0.11.13 \
    PATH="/opt/venv/bin:$PATH" \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

# git/gcc/g++: uv sync compiles sdists (webrtcvad) and fetches PyOgg from git.
# ffmpeg, libopus, libsndfile: audio encode/decode used by the listen/sync APIs.
# curl: matches the production runtime image (healthchecks / tooling).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      gcc \
      g++ \
      make \
      pkg-config \
      ffmpeg \
      curl \
      libjemalloc2 \
      libopus0 \
      libopus-dev \
      libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir "uv==${UV_VERSION}" \
 && /opt/venv/bin/uv pip sync /src/backend/pylock.toml --python /opt/venv/bin/python --compile-bytecode \
 && /opt/venv/bin/python -m compileall -q -j 0 -x '(^|/)tests/' /src/backend || true

WORKDIR /src

# webrtcvad imports pkg_resources, which setuptools 82 removed from the top level.
# Pin <81 after `uv pip sync` (the lock currently resolves setuptools 82).
RUN /opt/venv/bin/pip install --no-cache-dir 'setuptools>=70,<81'

# Cheap offline smoke. Do not abort the image build if a test fails.
# ENCRYPTION_SECRET is the dummy value backend/test.sh uses; not a production secret.
RUN ENCRYPTION_SECRET="omi_ZwB2ZNqB2HHpMK6wStk7sTpavJiPTFg7gXUHnc4tFABPU6pZ2c2DKgehtfgi4RZv" \
    OPENAI_API_KEY="test-openai-key-not-real" \
    python -c "import fastapi, firebase_admin, stripe, opuslib, webrtcvad, pytest, fakeredis, fake_firestore, uvicorn" \
 && cd /src/backend \
 && (python -m pytest -q -m "not integration and not slow" \
       tests/unit/test_rate_limiting.py \
       tests/unit/test_ws_auth_handshake.py \
       tests/unit/test_webhook_auto_disable.py \
     || echo "WARNING: pytest reported failures")
