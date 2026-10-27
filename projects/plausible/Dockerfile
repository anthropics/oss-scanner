FROM clickhouse/clickhouse-server:25.11.5.8 AS clickhouse
FROM node:24.17.0-trixie-slim AS nodejs

FROM hexpm/elixir:1.20.4-erlang-28.5.0.5-debian-trixie-20260824

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    MIX_ENV=test \
    PERSISTENT_CACHE_DIR=/src/cached

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git build-essential \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-18 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=clickhouse /usr/bin/clickhouse /usr/bin/clickhouse
COPY --from=clickhouse /etc/clickhouse-server /etc/clickhouse-server
COPY --from=nodejs /usr/local/bin/node /usr/local/bin/node
COPY --from=nodejs /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && mkdir -p /var/lib/clickhouse /var/log/clickhouse-server

# config/.env.test connects as postgres:postgres and as ClickHouse's passwordless default user.
RUN pg_ctlcluster 18 main start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres'\"" \
    && pg_ctlcluster 18 main stop

RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'pg_isready -q -h 127.0.0.1 || pg_ctlcluster 18 main start' \
      'curl -sf http://127.0.0.1:8123/ping >/dev/null || clickhouse server --config-file=/etc/clickhouse-server/config.xml --daemon' \
      'timeout 120 sh -c "until pg_isready -q -h 127.0.0.1 && curl -sf http://127.0.0.1:8123/ping >/dev/null; do sleep 0.5; done"' \
      > /usr/local/bin/plausible-test-services \
    && chmod +x /usr/local/bin/plausible-test-services

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN mix local.hex --force && mix local.rebar --force && mix deps.get
RUN npm ci --prefix ./tracker && npm run deploy --prefix ./tracker
RUN npm ci --prefix ./assets
RUN mix compile && MIX_ENV=ce_test mix compile

# Migrate both editions' test databases and fetch tzdata while the network is up.
RUN plausible-test-services \
    && mix do ecto.create, ecto.migrate \
    && MIX_ENV=ce_test mix do ecto.create, ecto.migrate \
    && mix run -e "Tzdata.ReleaseUpdater.poll_for_update"

# Check that the image works without failing the build.
RUN plausible-test-services \
    && (mix test test/plausible_web/controllers/api/external_controller_test.exs || echo "WARNING: EE tests failed") \
    && (MIX_ENV=ce_test mix test test/plausible_web/controllers/api/external_controller_test.exs || echo "WARNING: CE tests failed")
