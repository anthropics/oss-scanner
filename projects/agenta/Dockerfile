# syntax=docker/dockerfile:1
# The build context is the Agenta repository root. Keep the entire checkout and
# development dependencies so the scanner can investigate and test code offline.
FROM ghcr.io/astral-sh/uv:0.11.14 AS uv
FROM node:24-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON=3.13 \
    UV_LINK_MODE=copy \
    UV_NATIVE_TLS=true \
    UV_HTTP_TIMEOUT=300 \
    NEXT_TELEMETRY_DISABLED=1 \
    TURBO_TELEMETRY_DISABLED=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    HF_HUB_OFFLINE=1 \
    NODE_OPTIONS=--max-old-space-size=6144

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git build-essential python3 python3-yaml \
      libpq-dev postgresql redis-server ripgrep jq \
    && rm -rf /var/lib/apt/lists/*
RUN uv python install 3.13 \
    && npm install --global corepack@0.31.0 \
    && corepack enable

COPY . /src
WORKDIR /src

# Each Python project has its own locked environment and local SDK/client sources.
RUN cd /src/api && uv sync --locked \
    && cd /src/services && uv sync --locked \
    && cd /src/sdks/python && uv sync --locked

# The runner is a separate pnpm project with its own version and dependency patches.
RUN cd /src/services/runner \
    && corepack prepare "$(node -p 'require("./package.json").packageManager')" --activate \
    && pnpm install --frozen-lockfile \
    && pnpm run build:extension

# Install the workspace so shared packages also have their development tools.
# Build only the current application and its dependency packages, not the retired
# desktop apps or the separate marketing website. Retain all source for reference.
RUN cd /src/web \
    && corepack prepare "$(node -p 'require("./package.json").packageManager')" --activate \
    && pnpm install --frozen-lockfile
RUN cd /src/web && pnpm run build-mobile

# No account, model provider key, external service, or production data is required.
# Tests are run separately with --network=none; see threat_model.md for commands.
WORKDIR /src
CMD ["bash"]
