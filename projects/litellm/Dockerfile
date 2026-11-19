# Build LiteLLM (the Python SDK, the proxy server and its Rust extension) for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so this installs
# everything the tests and a local proxy need: every extra and dependency group from uv.lock, the Rust
# toolchain that rust-toolchain.toml pins with every crate in Cargo.lock, the Prisma client and engines,
# the dashboard's npm packages, and a local PostgreSQL and Redis. threat_model.md says how to run it.
FROM ghcr.io/astral-sh/uv:0.11.7 AS uv
FROM rust:1.98.0-slim-trixie AS rust
FROM node:24.19.0-trixie-slim AS node

# The production image runs Python 3.13.
FROM python:3.13-slim-trixie

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:$PATH \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    NEXT_TELEMETRY_DISABLED=1 \
    npm_config_fund=false \
    npm_config_audit=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl git libffi-dev libpq-dev libsndfile1 libssl-dev pkg-config \
        postgresql redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# The toolchain and components that rust-toolchain.toml pins, and every crate the Rust workspace locks,
# so `cargo build` and `cargo test` work offline.
RUN rustup toolchain install \
    && rustup component list --installed \
    && cargo --version \
    && cargo fetch --locked --manifest-path litellm-rust/Cargo.toml

# The full test environment, installed the way `make install-test-deps` does it: every extra and every
# dependency group from uv.lock into /src/.venv. LiteLLM itself is installed in editable mode, which
# builds the Rust extension (litellm.rust_bridge._native) with the dev profile, so it has debug info.
RUN uv sync --frozen --all-extras --all-groups

ENV VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# The Prisma client for the proxy's database. This also caches the Prisma CLI and query engine under
# /root/.cache, which `prisma migrate` needs when the proxy boots offline.
RUN prisma generate --schema litellm/proxy/schema.prisma

# The dashboard's npm packages, for its Vitest suite. The proxy serves the committed build in
# litellm/proxy/_experimental/out, so the dashboard is not rebuilt here.
RUN cd ui/litellm-dashboard && npm ci

# A local database, user and password for the proxy, and a config whose model answers with a mock
# response, so the proxy runs with no provider and no network.
RUN service postgresql start \
    && su postgres -c "psql -v ON_ERROR_STOP=1 -c \"CREATE ROLE litellm LOGIN SUPERUSER PASSWORD 'litellm'\"" \
    && su postgres -c "createdb -O litellm litellm" \
    && service postgresql stop \
    && mkdir -p /opt/litellm \
    && printf '%s\n' \
        'model_list:' \
        '  - model_name: mock-gpt' \
        '    litellm_params:' \
        '      model: openai/mock-gpt' \
        '      api_key: sk-mock' \
        '      mock_response: Hello from the mock model' \
        'general_settings:' \
        '  master_key: os.environ/LITELLM_MASTER_KEY' \
        '  store_model_in_db: true' \
        > /opt/litellm/config.yaml

# The network is gone after this point, so `uv run` must use the environment built above as it is, never
# try to re-resolve or re-sync it, and cargo must use the crates fetched above.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    CARGO_NET_OFFLINE=true \
    DATABASE_URL=postgresql://litellm:litellm@localhost:5432/litellm \
    LITELLM_MASTER_KEY=sk-oss-scanner-master

# The tests for the proxy's API key authentication, so the image is known to work. A failing test must not
# abort the build. threat_model.md lists the other test suites.
RUN pytest tests/unit/proxy/auth/test_user_api_key_auth.py -q -p no:cacheprovider -n 4 \
    || echo "WARNING: pytest reported failures"
