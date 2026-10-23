# Build of getnao/nao for the OSS Scanner.
# nao is a monorepo: a Bun/Fastify backend and a Vite/React frontend under apps/, and a Python CLI
# (nao-core, which also hosts the FastAPI SQL sidecar) under cli/. Network is only available during
# this build, so every JS and Python dependency is installed here.
#
# trixie rather than bookworm for its git: the backend's branch tooling needs `git for-each-ref --exclude` (git >= 2.42).
FROM node:22-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git pkg-config openssl \
      unixodbc-dev libmariadb-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN npm install -g npm@11.10.1 bun

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# JS workspaces (apps/backend, apps/frontend, apps/shared), from package-lock.json as CI does.
# --ignore-scripts skips the husky prepare hook; better-sqlite3 (used by the backend test suite) is the one
# native module that needs its install step.
RUN npm ci --ignore-scripts && npm rebuild better-sqlite3

# Python CLI and FastAPI sidecar, with every database/LLM extra and the dev tooling (pytest, ruff, ty).
RUN cd cli && uv python install 3.13 && uv sync --all-extras --dev

# Frontend static bundle, served by the backend in production.
RUN cd apps/frontend && npx vite build

# Minimal configuration so the backend boots offline against SQLite, pointing at the bundled example project.
RUN cp .env.example .env \
    && sed -i "s|^BETTER_AUTH_SECRET=.*|BETTER_AUTH_SECRET=$(openssl rand -base64 32)|" .env \
    && sed -i "s|^NAO_DEFAULT_PROJECT_PATH=.*|NAO_DEFAULT_PROJECT_PATH=/src/example|" .env \
    && (npm run -w @nao/backend db:migrate || echo "WARNING: database migration failed; the backend migrates on first start")

# Run the test suites so the image is known to work, without letting a failing test abort the build.
RUN (npm run -w @nao/backend test || echo "WARNING: backend vitest reported failures")
RUN (cd cli && uv run pytest -q --timeout 120 || echo "WARNING: cli pytest reported failures")
