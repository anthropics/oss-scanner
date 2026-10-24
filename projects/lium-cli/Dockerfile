# Builds the Lium Python SDK and CLI (package lium.io) the way its CI does: uv sync from the frozen uv.lock with
# the dev and provider extras, then the unit tests under test/. The e2e/ suite needs the live API and is not run.
FROM python:3.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git jq openssh-client rsync build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /usr/local/bin/

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# UV_PYTHON pins the image's interpreter so uv does not download its own. The venv goes on PATH,
# so `lium` and `pytest` work offline after the build.
ENV UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH
RUN uv sync --frozen --extra dev --extra provider && lium --help >/dev/null

# Cheap tests, so a broken image is visible in the build log without failing the build.
RUN cd /src && (pytest test/ -q -p no:cacheprovider || echo "WARNING: pytest reported failures")
