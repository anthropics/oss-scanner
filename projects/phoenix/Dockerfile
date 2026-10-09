# Builds Arize Phoenix (Python server + React web app) for the OSS Scanner.
# Network access is available here and removed afterwards, so every dependency the tests need is installed now.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON=3.11 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PNPM_HOME=/pnpm \
    PATH=/src/.venv/bin:/pnpm:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git curl pkg-config libpq-dev postgresql \
    && rm -rf /var/lib/apt/lists/*
# Keep in step with the lower bound of [tool.uv] required-version in pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /usr/local/bin/

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Python: phoenix and its workspace packages (client, evals, otel) in editable mode, plus the unit-test requirements.
RUN uv python install 3.11 \
    && uv sync --all-extras --all-packages \
    && uv pip install -r requirements/unit-tests.txt

# Frontend: install the pnpm workspace and build the web app, which the server serves from src/phoenix/server/static.
RUN npm i -g corepack && corepack enable \
    && cd /src/js && corepack install \
    && pnpm install --frozen-lockfile \
    && pnpm --filter 'phoenix-ui...' run build

# Smoke-test the image (the full suite is `cd tests && pytest unit/`); a failing test does not abort the build.
RUN cd /src/tests && (timeout 600 python -m pytest unit/server/api/routers/test_auth_md.py -q -p no:xdist \
      || echo "WARNING: phoenix unit tests reported failures")
