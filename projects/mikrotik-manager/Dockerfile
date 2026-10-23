# MikroTik Manager: a self-hosted web app (Node/TypeScript backend, React frontend)
# that manages MikroTik RouterOS devices. Production runs it in Docker Compose with
# PostgreSQL, Redis, InfluxDB and nginx; this image builds both halves, runs the
# unit tests, and installs PostgreSQL and Redis so the API can be started offline
# with `mtm-start` (see threat_model.md).
FROM node:26-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl postgresql redis-server \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install exactly the lockfiles and build, as the project's CI does.
RUN cd /src/backend && npm ci && npm run build
RUN cd /src/frontend && npm ci && npm run build

# Unit tests need no database or network. Two workers (ts-jest type-checks each
# suite, and one worker per CPU exhausts memory), a time limit so a stuck test can't
# stall the build, and a test failure doesn't fail the image.
RUN cd /src/backend && (timeout 1200 npx jest --ci --maxWorkers=2 --forceExit \
      || echo "WARNING: backend tests reported failures or timed out")
RUN cd /src/frontend && (timeout 600 npx vitest run --maxWorkers=2 \
      || echo "WARNING: frontend tests reported failures or timed out")

# A local database for running the API. Trust auth on localhost only; this image
# is a test environment, never a deployment.
RUN PGBIN="$(ls -d /usr/lib/postgresql/*/bin | head -1)" \
    && mkdir -p /var/lib/mtm-pg && chown postgres:postgres /var/lib/mtm-pg \
    && su postgres -c "$PGBIN/initdb -D /var/lib/mtm-pg -A trust -U postgres" >/dev/null

# mtm-start: start PostgreSQL and Redis, then the API on http://127.0.0.1:3001.
# Migrations run at startup and seed admin/admin (a password change is forced on
# first login). Test-only secrets; InfluxDB (metrics) is absent, which the app tolerates.
RUN printf '%s\n' \
  '#!/bin/sh' \
  'set -e' \
  'PGBIN="$(ls -d /usr/lib/postgresql/*/bin | head -1)"' \
  'su postgres -c "$PGBIN/pg_ctl -D /var/lib/mtm-pg -l /tmp/postgres.log -w start" >/dev/null' \
  'su postgres -c "createdb mtm" 2>/dev/null || true' \
  'redis-server --daemonize yes --bind 127.0.0.1 >/dev/null' \
  'mkdir -p /tmp/mtm/backups /tmp/mtm/secrets' \
  'cd /src/backend' \
  'export DATABASE_URL=postgres://postgres@127.0.0.1:5432/mtm REDIS_URL=redis://127.0.0.1:6379' \
  'export JWT_SECRET=scanner-test-jwt-secret-0123456789abcdef ENCRYPTION_KEY=scanner-test-encryption-key-0123456789' \
  'export CORS_ORIGIN=http://127.0.0.1:3001 PORT=3001 NODE_ENV=production BACKUPS_DIR=/tmp/mtm/backups SECRETS_DIR=/tmp/mtm/secrets INFLUXDB_URL=http://127.0.0.1:8086' \
  'exec node dist/index.js "$@"' \
  > /usr/local/bin/mtm-start && chmod +x /usr/local/bin/mtm-start
