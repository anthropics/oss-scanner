# MCP Python SDK, installed and tested the way its CI (.github/workflows/shared.yml) does: uv sync from the committed
# uv.lock with every extra and the default groups, then pytest. The trixie image includes git, which the
# version needs (uv-dynamic-versioning reads git tags).
FROM ghcr.io/astral-sh/uv:python3.13-trixie

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    COLUMNS=150

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# --all-packages also installs the example servers and clients, which are useful to exercise the SDK. strict-no-cover is
# a coverage linter that is fetched from git and is not used by the tests.
RUN uv sync --frozen --all-extras --all-packages --no-install-package strict-no-cover

# There is no network when the scanner runs, so `uv run` must use the environment above as it is.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# A failing test must not abort the image build.
RUN timeout 1200 pytest -n auto -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
