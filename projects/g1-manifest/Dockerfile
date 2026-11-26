# Builds G1-Manifest and caches all Python dependencies for offline security analysis
FROM docker.io/library/python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      openssl \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Install package, optional host-scan dependency, and pytest while online
RUN pip install --no-cache-dir -e ".[host]" pytest

# Baseline unit, integration, hardening, and consumer conformance tests
RUN pytest -v tests/ conformance/

CMD ["bash"]
