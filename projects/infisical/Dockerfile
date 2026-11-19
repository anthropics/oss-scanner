# Infisical build for the OSS Scanner.
#
# Builds the Node.js API (backend/), the React frontend (frontend/) and the Go port of the API
# (backend-go/) while network access is available. The scan runs offline, so everything the
# builds and test suites need is fetched here.
#
# Postgres and Redis are installed and configured for the backend e2e suite, but nothing starts
# them. Run `infisical-test-services` first. threat_model.md says how to run the tests.

FROM golang:1.26-trixie AS go-toolchain

FROM node:26.10.0-trixie
COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}" \
    DEBIAN_FRONTEND=noninteractive

# The backend's native modules, such as odbc and pkcs11js, build against these. Postgres and Redis back the e2e suite.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential python3 pkg-config perl procps git wget \
      libssl-dev openssl openssh-client \
      unixodbc unixodbc-dev freetds-dev freetds-bin tdsodbc \
      postgresql postgresql-contrib redis-server \
    && rm -rf /var/lib/apt/lists/*

RUN printf "[FreeTDS]\nDescription = FreeTDS Driver\nDriver = /usr/lib/$(uname -m)-linux-gnu/odbc/libtdsodbc.so\nSetup = /usr/lib/$(uname -m)-linux-gnu/odbc/libtdsS.so\nFileUsage = 1\n" > /etc/odbcinst.ini

# The PQC (ML-DSA / SLH-DSA) certificate code calls OpenSSL 3.5 from /opt/openssl-pqc. The version and
# checksum match the repository's own Dockerfiles.
WORKDIR /tmp/openssl-pqc-build
RUN wget -q https://github.com/openssl/openssl/releases/download/openssl-3.5.6/openssl-3.5.6.tar.gz \
    && echo "deae7c80cba99c4b4f940ecadb3c3338b13cb77418409238e57d7f31f2a3b736  openssl-3.5.6.tar.gz" | sha256sum -c - \
    && tar -xf openssl-3.5.6.tar.gz \
    && cd openssl-3.5.6 \
    && ./Configure --prefix=/opt/openssl-pqc --openssldir=/opt/openssl-pqc/ssl no-docs \
    && make -j"$(nproc)" \
    && make install_sw \
    && cd / && rm -rf /tmp/openssl-pqc-build

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN cd backend && npm ci && NODE_OPTIONS=--max-old-space-size=8192 npm run build
RUN cd frontend && npm ci && NODE_OPTIONS=--max-old-space-size=8192 npm run build

# vet compiles the unit and integration test code without running it (integration TestMain needs Docker).
RUN cd backend-go \
    && go mod download \
    && go build -o infisical ./cmd/infisical/... \
    && (go vet ./... && go vet -tags integration ./tests/... || echo "WARNING: go vet reported problems")

# Postgres is set up as in docker-compose.test.yml, with an "infisical" superuser and the test database.
RUN PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1) \
    && echo "max_locks_per_transaction = 512" > "/etc/postgresql/$PG_VERSION/main/conf.d/infisical.conf" \
    && pg_ctlcluster "$PG_VERSION" main start \
    && su postgres -c "psql -c \"CREATE USER infisical WITH SUPERUSER PASSWORD 'infisical'\"" \
    && su postgres -c "createdb -O infisical infisical-test" \
    && pg_ctlcluster "$PG_VERSION" main stop

RUN printf '%s\n' \
      '#!/usr/bin/env bash' \
      '# Starts the Postgres and Redis the backend e2e suite expects. Safe to run more than once.' \
      'set -euo pipefail' \
      'PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)' \
      'pg_isready -q -h localhost -p 5432 || pg_ctlcluster "$PG_VERSION" main start' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes --save "" --appendonly no --dir /tmp' \
      'for _ in $(seq 1 30); do' \
      '  if pg_isready -q -h localhost -p 5432 && redis-cli ping >/dev/null 2>&1; then echo "Postgres and Redis are ready"; exit 0; fi' \
      '  sleep 1' \
      'done' \
      'echo "Timed out waiting for Postgres and Redis" >&2' \
      'exit 1' \
      > /usr/local/bin/infisical-test-services \
    && chmod +x /usr/local/bin/infisical-test-services

# The e2e harness reads these test-only values from /src/.env.test. The keys come from .env.test.example.
# Each run drops and recreates the schema of the database it is given.
RUN printf '%s\n' \
      'DB_CONNECTION_URI=postgres://infisical:infisical@localhost:5432/infisical-test?sslmode=disable' \
      'REDIS_URL=redis://localhost:6379' \
      'AUTH_SECRET=4bnfe4e407b8921c104518903515b218' \
      'ENCRYPTION_KEY=4bnfe4e407b8921c104518903515b218' \
      > /src/.env.test
ENV TELEMETRY_ENABLED="false" \
    NODE_OPTIONS="--max-old-space-size=4096"

# Quick checks that the image works. A failure prints a warning and the build carries on.
RUN cd backend && (npm run test:unit || echo "WARNING: backend unit tests reported failures")
RUN cd backend-go && (go test -count=1 -timeout 300s ./internal/... || echo "WARNING: backend-go unit tests reported failures")
RUN infisical-test-services \
    && (cd backend && npm run test:e2e -- e2e-test/routes/v1/login.spec.ts || echo "WARNING: backend e2e smoke test reported failures") \
    && pg_ctlcluster "$(ls /etc/postgresql | sort -V | tail -n 1)" main stop \
    && (redis-cli shutdown nosave || true)
