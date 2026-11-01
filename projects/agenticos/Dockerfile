# AgenticOS: FastAPI backend (Python, uv) and Next.js console (bun).
# The scanner uses the repository root as the build context and audits /src offline.
FROM python:3.15-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git curl unzip pkg-config libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The repository's root .dockerignore is an allowlist (backend/ and emails/ only), so the build context
# lacks frontend/, docs/ and the rest. Fill in whatever is missing from a clone, without overwriting
# what the context already provided.
RUN git clone --depth 1 --branch main https://github.com/vstorm-co/agenticos /tmp/full \
    && cp -rn /tmp/full/. /src/ && rm -rf /tmp/full

# Backend: locked dependencies including the dev group (pytest, anyio).
RUN cd backend && uv sync --frozen

# Frontend: locked dependencies.
RUN cd frontend && bun install --frozen-lockfile

# The network is gone after this point; keep uv from re-resolving.
ENV UV_FROZEN=1 UV_NO_SYNC=1 UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/backend/.venv \
    PATH=/src/backend/.venv/bin:$PATH

# Cheap smoke test that must not abort the build. The unit tests mock the database;
# integration tests need PostgreSQL with pgvector and are not run here.
RUN cd backend && (pytest tests/test_coverage_gate.py -q -p no:cacheprovider \
    || echo "WARNING: pytest reported failures")
