FROM python:3.14-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git curl libpq-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv==0.13.6 && uv venv /opt/venv

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/services/web/server

# installs the webserver and the repo packages it depends on (editable)
RUN uv pip install --requirement requirements/ci.txt

# Cheap tests that need no external services; failures do not abort the build.
RUN (python -m pytest tests/unit/isolated -x -q -p no:cacheprovider || echo "WARNING: unit tests reported failures")
