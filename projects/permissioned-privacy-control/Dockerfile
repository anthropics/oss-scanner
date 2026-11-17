# Builds Permissioned Privacy Control (Open Privacy Suite) from the checkout at /src and keeps everything needed to
# build and test it offline: the Go module caches (main module and mcp/), the admin UI's node_modules, and a local
# PostgreSQL 15 for the database-backed tests. Go and Node versions match the project's CI.
FROM docker.io/library/golang:1.26.11-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

# build-essential and libgmp-dev: go-rapidsnark (ZK proof verification) needs CGO and GMP, as in Dockerfile.backend.
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg git make jq procps build-essential libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# PostgreSQL 15, the version CI uses (postgres:15-alpine), from the PostgreSQL apt repository. The scanner has no
# Docker, so the Go tests use this server through TEST_DATABASE_URL and E2E_DATABASE_URL (fresh child databases)
# instead of testcontainers. Local connections are trusted: the server only listens on localhost inside the image.
RUN install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL --retry 5 --retry-all-errors --retry-delay 3 -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-15 \
    && rm -rf /var/lib/apt/lists/* \
    && printf '%s\n' 'local all all trust' 'host all all 127.0.0.1/32 trust' 'host all all ::1/128 trust' \
         > /etc/postgresql/15/main/pg_hba.conf
ENV TEST_DATABASE_URL=postgres://postgres@localhost:5432/privacy_proxy_test?sslmode=disable \
    E2E_DATABASE_URL=postgres://postgres@localhost:5432/privacy_proxy_test?sslmode=disable

# `ops-start-postgres` starts the local server and creates the test database. Run it before any database test.
RUN printf '%s\n' \
      '#!/bin/sh' \
      'set -eu' \
      'pg_ctlcluster 15 main status >/dev/null 2>&1 || pg_ctlcluster 15 main start' \
      'tries=0' \
      'until pg_isready -q -h localhost -p 5432; do' \
      '  tries=$((tries + 1)); [ "$tries" -lt 30 ] || { echo "PostgreSQL did not start" >&2; exit 1; }; sleep 1' \
      'done' \
      'psql -h localhost -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '"'"'privacy_proxy_test'"'"'" | grep -q 1 \' \
      '  || createdb -h localhost -U postgres privacy_proxy_test' \
      > /usr/local/bin/ops-start-postgres \
    && chmod 0755 /usr/local/bin/ops-start-postgres

# Node.js for the admin UI (frontend/), at the version CI pins.
COPY --from=docker.io/library/node:24.22.3-trixie /usr/local/bin/node /usr/local/bin/node
COPY --from=docker.io/library/node:24.22.3-trixie /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version

COPY . /src
WORKDIR /src

# Downloads are retried: one network blip should not fail the whole build.
RUN for i in 1 2 3; do go mod download && (cd mcp && go mod download) && exit 0; sleep 10; done; exit 1

# The server as it ships (without the mockauth tag, so no mock authentication), then every package.
RUN go build -o /usr/local/bin/privacy-proxy ./cmd/server \
    && go build ./... \
    && (cd mcp && go build ./...)

RUN cd frontend && npm ci --no-audit --no-fund --fetch-retries=5

# Baseline tests, logged so a scan can tell which tests already fail here. -p 1 is required: the packages share one
# database and clear its tables between tests. A failing test must not abort the build.
RUN ops-start-postgres \
    && (go test ./internal/... -p 1 -count=1 -timeout 20m > /var/log/ops-go-tests.log 2>&1 \
        || echo 'WARNING: Go baseline tests reported failures, see /var/log/ops-go-tests.log'); \
    pg_ctlcluster 15 main stop || true
RUN cd frontend && (npm run test:run > /var/log/ops-frontend-tests.log 2>&1 \
    || echo 'WARNING: frontend tests reported failures, see /var/log/ops-frontend-tests.log')

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=readonly

CMD ["bash"]
