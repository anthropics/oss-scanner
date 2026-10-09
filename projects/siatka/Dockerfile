# siatka: pure-Python (stdlib only) deterministic safety filter for Polish text.
# Requires Python >= 3.12 (debian:bookworm ships 3.11), hence the official python image.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
# The package has zero runtime dependencies; pytest is fetched now because the audit runs offline.
RUN pip install --no-deps -e /src && pip install pytest
RUN (python -m pytest -q tests || echo "WARNING: tests reported failures")
