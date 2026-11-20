FROM node:24-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq procps \
        build-essential pkg-config \
        python3 python3-dev python3-venv python-is-python3 \
        libcairo2-dev libgirepository-2.0-dev \
        gir1.2-ostree-1.0 gir1.2-appstream-1.0 \
        libpq-dev libpq5 \
        postgresql postgresql-client \
        redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY . /src
WORKDIR /src

RUN cd /src/backend \
    && uv sync --frozen --all-groups
ENV PATH="/src/backend/.venv/bin:${PATH}"

RUN cd /src/backend-node \
    && corepack enable \
    && pnpm install --frozen-lockfile \
    && pnpm build
RUN cd /src/backend-node \
    && (pnpm test || echo "WARNING: backend-node tests reported failures")

RUN cd /src/frontend \
    && corepack enable \
    && pnpm install --frozen-lockfile \
    && pnpm build
RUN cd /src/frontend \
    && (pnpm test || echo "WARNING: frontend tests reported failures")

RUN set -eux; \
    service postgresql start; \
    su postgres -c "psql -v ON_ERROR_STOP=1 -c \"ALTER USER postgres PASSWORD 'postgres'\""; \
    su postgres -c "createdb flathub"; \
    DB="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/flathub"; \
    export DATABASE_URL="$DB" \
           DATABASE_REPLICA_URL="$DB" \
           MAINTENANCE_TEST_DATABASE_URL="$DB" \
           PERMISSION_ASSESSMENT_TEST_DATABASE_URL="$DB" \
           STATS_TEST_DATABASE_URL="$DB"; \
    cd /src/backend; \
    uv run alembic upgrade head; \
    (uv run pytest -vvvv \
        --ignore=tests/main.py \
        --ignore=tests/test_storefront_smoke.py \
        --ignore=tests/test_year_in_review_smoke.py \
        --ignore=tests/api_smoke \
        || echo "WARNING: backend unit tests reported failures"); \
    service postgresql stop || true

WORKDIR /src
CMD ["bash"]
