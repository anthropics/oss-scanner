# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here, from the committed uv.lock, as CI does.
FROM ghcr.io/astral-sh/uv:python3.13-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY . /src
WORKDIR /src

# Every workspace package with every extra, as `make install` does, except `mcp-tasks` (it conflicts with
# the `dev` group) and `sentence-transformers` (it pulls PyTorch and several gigabytes of CUDA libraries).
RUN uv sync --frozen --all-packages --all-extras --no-extra mcp-tasks --no-extra sentence-transformers

# The network is gone after this point, so `uv run` must use the environment above as it is.
# `TYPECHECK_EXAMPLES=false` stops the docs tests from running pyright, which needs Node.js.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    TYPECHECK_EXAMPLES=false \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run the test suite so the image is known to work; a failing or slow test must not abort the build.
# Eight workers keep memory use bounded: every worker imports every provider SDK.
RUN timeout 1200 pytest -n 8 --dist=loadgroup -q --tb=line -p no:cacheprovider || echo "WARNING: pytest reported failures"
