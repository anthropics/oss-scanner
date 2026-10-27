# Build Django Ninja for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here. This mirrors the project's coverage CI job (.github/workflows/test.yml):
# Python 3.12, the pinned uv version, and the locked "test" dependency group.
FROM python:3.12-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The uv version CI pins.
RUN pip install --no-cache-dir "uv==0.11.32"

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# django-ninja itself (editable) plus pytest, pytest-django, pytest-asyncio and the rest of the test group,
# from the committed lock file into /src/.venv. Django resolves to the newest locked release.
RUN uv sync --locked --no-default-groups --group test

# The network is gone after this point, so `uv run` must use the environment built above as it is,
# never try to re-resolve or re-sync it.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run the test suite so the image is known to work; a failing test must not abort the build.
# The tests use SQLite, so no database server is needed. Further tests: `pytest tests/<file>`.
RUN pytest tests -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
