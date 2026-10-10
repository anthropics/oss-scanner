FROM node:24-bookworm-slim AS node
FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.12-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    RAGWELD_LOAD_DOTENV=0 \
    RAGWELD_DISABLE_PROFILING=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git build-essential pkg-config \
      libgl1 libglib2.0-0t64 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra dev --extra flyte --no-install-project
COPY web/package.json web/package-lock.json ./web/
# Match the npm 10 lockfile behavior used by the project's Node 20 CI while
# retaining Node 24 for the TypeScript unit-test runner.
RUN npm install --global npm@10.8.2 --no-audit --no-fund \
    && npm --prefix web ci --no-audit --no-fund
RUN cd web && npx playwright install --with-deps chromium

# Keep source, tests, fixtures, catalogs, and history available to the auditor.
# Anthropic builds this from an anonymous clone of the public repository.
COPY . /src
RUN uv sync --frozen --extra dev --extra flyte \
    && npm --prefix web run build

ENV PATH="/src/.venv/bin:${PATH}" \
    UV_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
CMD ["bash"]
