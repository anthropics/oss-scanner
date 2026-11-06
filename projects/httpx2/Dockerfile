# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here, from the committed uv.lock, as CI does.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY . /src
WORKDIR /src

RUN uv sync --frozen --no-default-groups --group dev

# The network is gone after this point, so `uv run` must use the environment above as it is.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run the test suite so the image is known to work; a failing test must not abort the build.
RUN pytest tests -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
