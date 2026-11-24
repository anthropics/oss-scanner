# Builds G1-Docket and caches all Python dependencies for offline vulnerability analysis
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      build-essential \
      git \
      python3 \
      python3-pip \
      python3-dev \
      python3-venv \
      pkg-config \
      libssl-dev \
      libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# The scanner copies the checkout to /src
COPY . /src
WORKDIR /src

# Set up virtual environment and install all dependencies online
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel \
    && pip install -e . \
    && pip install pytest pytest-asyncio httpx build

# Pre-build wheel and run baseline test suite
RUN python -m build --wheel --outdir /tmp/dist \
    && (pytest -v tests/ conformance/ || echo "WARNING: baseline tests reported failures")

# Ensure all future agent patches and reproducers execute strictly offline
ENV PIP_NO_INDEX=1

CMD ["bash"]
