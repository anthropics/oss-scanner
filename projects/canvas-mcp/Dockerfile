# Build Canvas MCP for Anthropic's OSS Scanner.
# Canvas MCP is a Python MCP server for Canvas LMS (src/canvas_mcp/) with a small TypeScript code API
# (src/canvas_mcp/code_api/). The scanner uses the repository root as the build context and audits /src
# offline, so this installs everything the tests need. It mirrors the project's CI
# (.github/workflows/canvas-mcp-testing.yml): the Python suite (job `test`) and the code API (job
# `test-code-api`). Python 3.14 is the newest version in the CI matrix and the one the project's own
# Dockerfile ships. No Canvas instance and no Canvas token are needed: the tests mock every Canvas call.
FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM node:24-bookworm-slim AS node

FROM python:3.14-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.14 \
    npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update_notifier=false

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version && uv --version

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Canvas MCP itself (editable), the default `dev` dependency group (pytest, pytest-asyncio, PyYAML, ruff,
# mypy) and the `hosted` extra (the Azure SDKs that the HTTP-mode access-request code imports lazily; the
# project's own Dockerfile installs it too), all from the committed uv.lock into /src/.venv.
RUN uv sync --locked --extra hosted

# The code API's npm packages (tsx, TypeScript, Node types) from package-lock.json, then a build into dist/.
# With tsx in /src/node_modules, `execute_typescript` in local mode and `npm test` both work offline.
RUN npm ci && npm run build

# The network is gone after this point, so `uv run` must use the environment built above as it is, never
# try to re-resolve or re-sync it. FASTMCP_MCP_CAMELCASE_COMPAT=false matches CI.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH \
    FASTMCP_MCP_CAMELCASE_COMPAT=false

# Run both suites so the image is known to work; a failing test must not abort the build.
RUN python -m pytest tests/ -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
RUN npm test || echo "WARNING: npm test reported failures"
