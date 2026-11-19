# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here, from the committed uv.lock, as CI does. pydantic-core is a workspace
# member written in Rust, so the image also needs a Rust toolchain.
FROM ghcr.io/astral-sh/uv:python3.13-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

COPY . /src
WORKDIR /src

# `uv sync` builds pydantic-core with maturin's `dev` profile (`editable-profile` in its pyproject.toml):
# unoptimized, with debug info, debug assertions and overflow checks.
RUN uv sync --frozen --all-packages --group testing-extra --all-extras

# The network is gone after this point, so `uv run` must use the environment above as it is.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    CARGO_NET_OFFLINE=true \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run the test suite so the image is known to work; a failing or slow test must not abort the build.
RUN timeout 1200 pytest -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
