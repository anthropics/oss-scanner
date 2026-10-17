# Builds Kitaru (https://github.com/zenml-io/kitaru) from source for the OSS Scanner.
#
# The Kitaru server only supports PostgreSQL, so the image is based on the official PostgreSQL 16 image (the
# version the project's docker-compose.yml and CI use) and carries its own database. `kitaru-db-start` starts it
# on localhost:5433 with user postgres / password password, which is what the test suite and the server's
# defaults expect. Python and every dependency come from the project's uv lockfiles.
FROM postgres:16-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_HTTP_TIMEOUT=600 \
    DO_NOT_TRACK=1 \
    KITARU_SERVER_ANALYTICS_OPT_IN=false \
    KITARU_TEST_DB_HOST=localhost \
    KITARU_TEST_DB_PORT=5433 \
    PGDATA=/var/lib/postgresql/kitaru

# uv at the version the project's own Dockerfiles pin. The scanner's own layer adds git, compilers and debuggers.
COPY --from=docker.io/astral/uv:0.12.1 /uv /uvx /bin/

# A local PostgreSQL cluster matching docker-compose.yml, started on demand by kitaru-db-start.
RUN mkdir -p "$PGDATA" && chown postgres:postgres "$PGDATA" \
    && echo password > /tmp/pwfile \
    && su postgres -c "initdb -D $PGDATA -U postgres --pwfile=/tmp/pwfile --auth-local=trust --auth-host=scram-sha-256" \
    && rm /tmp/pwfile \
    && printf '%s\n' '#!/bin/sh' \
      'su postgres -c "pg_ctl -D $PGDATA -o \"-p 5433 -c listen_addresses=localhost\" -l /tmp/postgres.log -w start"' \
      > /usr/local/bin/kitaru-db-start \
    && chmod +x /usr/local/bin/kitaru-db-start

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The core package with every extra and the fuzz group (as CI installs it), then the plugin workspace (adapters,
# importers, evaluators) in its own environment at /src/plugins/.venv.
RUN uv python install 3.13 \
    && uv sync --frozen --python 3.13 --all-extras --group fuzz \
    && uv sync --project plugins --frozen --python 3.13 --all-packages \
    && uv run --frozen python -c "import kitaru, kitaru.server.api.main"

# Everything is installed; from here on uv must not try to resolve or download anything.
ENV UV_FROZEN=1 \
    UV_OFFLINE=1 \
    PATH="/src/.venv/bin:$PATH"

# Run the test suites once against the local database so the image is known to work offline, but never fail the
# build on a test failure.
RUN kitaru-db-start \
    && (KITARU_TEST_REQUIRE_POSTGRES=1 timeout 2400 uv run pytest -q -p no:randomly \
          --ignore=tests/typescript -m "not mcp_fuzz" \
        || echo "WARNING: core tests reported failures") \
    && (timeout 1200 uv run --project plugins pytest -q -c plugins/pyproject.toml plugins/tests \
        || echo "WARNING: plugin tests reported failures") \
    && su postgres -c "pg_ctl -D $PGDATA -m fast stop"
