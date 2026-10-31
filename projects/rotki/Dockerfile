# OSS Scanner build for rotki (https://github.com/rotki/rotki).
#
# rotki's own top-level Dockerfile produces a distroless runtime image with no sources, shell or
# toolchain, so it is not usable here. This one keeps the checkout at /src and leaves all three
# parts of the project built in place, with every dependency fetched so it works offline:
#   - the python backend (rotkehlchen/), in a uv-managed virtualenv at /src/.venv
#   - the rust services (colibri, starling), debug builds in /src/target/debug
#   - the Vue/Electron frontend (frontend/), with node_modules installed and the web bundle built

# node's full bookworm image is buildpack-deps: it already carries gcc, make, git, curl and pkg-config
FROM node:24.20.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential pkg-config libssl-dev git curl jq sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# rust toolchain, the same version rotki's release image builds with
COPY --from=rust:1.91-bookworm /usr/local/cargo /usr/local/cargo
COPY --from=rust:1.91-bookworm /usr/local/rustup /usr/local/rustup
# uv manages the python interpreter and the virtualenv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/src/.venv/bin:/usr/local/cargo/bin:$PATH \
    UV_PYTHON=3.14t \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_LINK_MODE=copy \
    CYPRESS_INSTALL_BINARY=0 \
    NODE_OPTIONS=--max-old-space-size=4096

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# --- python backend -------------------------------------------------------------------------------
# Free-threaded CPython 3.14, as in rotki's CI. `--group dev` brings pytest and the test plugins.
RUN uv sync --locked --group dev \
    && uv run --no-sync python -c "import sys; from rotkehlchen.db.misc import detect_sqlcipher_version; sys.exit(0 if detect_sqlcipher_version() == 4 else 1)"

# --- rust services --------------------------------------------------------------------------------
# Debug profile on purpose: symbols and overflow checks help when reproducing a finding.
RUN cargo build --locked -p colibri -p starling
RUN cargo test --locked --workspace --no-run || echo "WARNING: could not prebuild the rust tests"

# --- frontend -------------------------------------------------------------------------------------
RUN cd frontend \
    && npm install -g corepack@latest \
    && corepack enable \
    && pnpm install --frozen-lockfile \
    && pnpm run docker:build

# --- test data ------------------------------------------------------------------------------------
# The backend tests replay recorded HTTP traffic (VCR cassettes) kept in a separate repository.
# Without it almost every decoder / exchange / api test needs the network.
RUN git clone --depth 1 --branch develop https://github.com/rotki/test-caching.git /opt/test-caching

# Cheap smoke test. It also makes pytest fetch the accounting rules it caches on first run, so later
# runs work offline. A failure here is reported but does not abort the build.
RUN CI=true CASSETTES_DIR=/opt/test-caching uv run --no-sync pytest -q \
      rotkehlchen/tests/unit/test_fval.py rotkehlchen/tests/unit/test_base58.py rotkehlchen/tests/unit/test_args.py \
    || echo "WARNING: backend smoke tests reported failures"

# Everything is fetched: from here on nothing should try to reach the network.
ENV UV_OFFLINE=1 \
    UV_NO_SYNC=1 \
    CARGO_NET_OFFLINE=true \
    CASSETTES_DIR=/opt/test-caching
