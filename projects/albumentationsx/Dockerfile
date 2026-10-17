FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    ALBUMENTATIONS_NO_TELEMETRY=1 \
    HF_HUB_OFFLINE=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PATH="/src/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-default-groups \
        --group ci-test --group ci-torch-cpu --extra headless --extra hub
