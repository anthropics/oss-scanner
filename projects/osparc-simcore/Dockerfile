FROM python:3.14-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git curl libpq-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv==0.13.6

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# One venv per service since each pins its own dependency versions.
# Repo packages are editable installs, so edits under /src take effect.
# Usage: /opt/venvs/<name>/bin/python -m pytest services/<dir>/tests/unit
RUN set -e; \
    for d in services/*/ services/web/server/ packages/service-integration/; do \
      [ -f "$d/requirements/dev.txt" ] || continue; \
      name=$(basename "$d"); \
      [ "$name" = "server" ] && name=webserver; \
      uv venv /opt/venvs/$name; \
      (cd "$d" && VIRTUAL_ENV=/opt/venvs/$name uv pip install --requirement requirements/dev.txt); \
    done

# Cheap tests that need no external services; failures do not abort the build.
RUN cd services/web/server && (/opt/venvs/webserver/bin/python -m pytest \
      tests/unit/isolated -x -q -p no:cacheprovider \
      || echo "WARNING: unit tests reported failures")
