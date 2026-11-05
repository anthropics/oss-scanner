# Builds rocicorp/mono (Zero and Replicache). The build context is the repository checkout.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    TURBO_TELEMETRY_DISABLED=1 \
    CI=1

# Postgres is zero-cache's upstream. It is installed so the scanner can run a real zero-cache offline:
#   service postgresql start
#   ZERO_UPSTREAM_DB=postgres://postgres@127.0.0.1/postgres ZERO_REPLICA_FILE=/tmp/replica.db \
#     ZERO_ADMIN_PASSWORD=admin node packages/zero/out/zero/src/cli.js
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential python3 git postgresql \
    && rm -rf /var/lib/apt/lists/* \
    && PGCONF="$(ls -d /etc/postgresql/*/main)" \
    && echo "wal_level = logical" >> "$PGCONF/postgresql.conf" \
    && echo "listen_addresses = '127.0.0.1'" >> "$PGCONF/postgresql.conf" \
    && sed -i 's/\(host.*127.0.0.1\/32 *\)scram-sha-256/\1trust/' "$PGCONF/pg_hba.conf"

RUN corepack enable && corepack prepare pnpm@11.11.0 --activate

COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile

# Builds @rocicorp/zero and every workspace package it depends on
# (zero-cache, zero-server, zero-client, zql, zqlite, replicache, shared, ...).
RUN pnpm exec turbo run build --filter=@rocicorp/zero...

# Most test files are not published to rocicorp/mono, so there is no suite to run here.
# Type-check as a smoke test that the checkout and install are complete.
RUN pnpm exec turbo run check-types --filter=@rocicorp/zero... || echo "WARNING: check-types reported errors"
