# Scanner image for https://github.com/hatchet-dev/hatchet (main).
#
# Builds the Go binaries in cmd/, the dashboard (frontend/app) and the Python and TypeScript SDKs, and installs the
# Postgres and RabbitMQ that the integration tests and a running server need, as docker-compose.yml provides them in
# development. The audit runs offline, so every dependency is fetched here. threat_model.md says how to use the image.
#
#   hatchet-services   starts Postgres (127.0.0.1:5431) and RabbitMQ (127.0.0.1:5672)
#   hatchet-server     starts both, then the API (:8080) and the engine (gRPC :7070), and writes a tenant API token

# go.mod pins the Go version. If this image's Go is older, the toolchain is downloaded here and stays in the module
# cache for offline use.
FROM golang:1.26-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq openssl procps \
      postgresql postgresql-contrib rabbitmq-server \
      python3 python3-venv python3-dev pipx \
    && rm -rf /var/lib/apt/lists/*

# Node.js for the dashboard and the TypeScript SDK, from the official image (Hatchet's .nvmrc and Dockerfiles use 24).
COPY --from=docker.io/library/node:24-trixie /usr/local/bin/node /usr/local/bin/node
COPY --from=docker.io/library/node:24-trixie /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && corepack enable \
    && pipx install poetry

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download

# Every server binary, as build/package/servers.dockerfile builds them, onto PATH. cmd/hatchet-loadtest/go would be
# written as "go" and shadow the toolchain. Login shells reset PATH, so it is restored for them.
RUN CGO_ENABLED=0 go build -o /usr/local/bin/ $(go list ./cmd/... | grep -v 'hatchet-loadtest/go$') \
    && hatchet-admin --help > /dev/null \
    && echo 'export PATH="/root/.local/bin:/go/bin:/usr/local/go/bin:$PATH"' > /etc/profile.d/toolchains.sh

# Compile every package and test binary once, untagged and with the tags CI uses, so later builds are fast.
# -exec /bin/true: compile and link only, because some TestMains start containers. -vet=off: a vet finding must not
# fail the build.
RUN go build ./... \
    && (go test -vet=off -exec /bin/true ./... || echo "WARNING: some test binaries do not compile") \
    && (go test -vet=off -exec /bin/true -tags integration ./... || echo "WARNING: some integration test binaries do not compile") \
    && (go test -vet=off -exec /bin/true -tags e2e ./... || echo "WARNING: some e2e test binaries do not compile")

# The dashboard, and the SDKs most deployments use. pnpm and poetry versions come from the lockfiles' projects.
RUN cd frontend/snippets && python3 -X utf8 generate.py \
    && cd ../app && pnpm install --frozen-lockfile && pnpm run build
RUN cd sdks/typescript && pnpm install --frozen-lockfile
RUN cd sdks/python && poetry install --all-extras --no-interaction

# Test certificates and encryption keys at the paths internal/testutils and the CI e2e jobs expect.
RUN bash hack/dev/generate-x509-certs.sh ./hack/dev/certs \
    && mkdir -p hack/dev/encryption-keys \
    && hatchet-admin keyset create-local-keys --key-dir ./hack/dev/encryption-keys

# Postgres as docker-compose.yml runs it: port 5431, user, password and database "hatchet".
RUN PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1) \
    && printf '%s\n' "port = 5431" "listen_addresses = '127.0.0.1'" "max_connections = 500" \
         > "/etc/postgresql/$PG_VERSION/main/conf.d/hatchet.conf" \
    && pg_ctlcluster "$PG_VERSION" main start \
    && su postgres -c "psql -p 5431 -c \"CREATE USER hatchet WITH SUPERUSER PASSWORD 'hatchet'\"" \
    && su postgres -c "createdb -p 5431 -O hatchet hatchet" \
    && DATABASE_URL='postgresql://hatchet:hatchet@127.0.0.1:5431/hatchet?sslmode=disable' hatchet-migrate \
    && pg_ctlcluster "$PG_VERSION" main stop

# RabbitMQ with the credentials docker-compose.yml sets. The user is created on first boot, so the node name the
# broker gets at run time does not matter.
RUN printf '%s\n' "default_user = user" "default_pass = password" "loopback_users = none" \
      > /etc/rabbitmq/rabbitmq.conf

RUN printf '%s\n' \
      '#!/usr/bin/env bash' \
      '# Starts Postgres (127.0.0.1:5431) and RabbitMQ (127.0.0.1:5672). Safe to run more than once.' \
      'set -euo pipefail' \
      'PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)' \
      'pg_isready -q -h 127.0.0.1 -p 5431 || pg_ctlcluster "$PG_VERSION" main start' \
      'rabbitmq-diagnostics -q ping >/dev/null 2>&1 || rabbitmq-server -detached' \
      'for _ in $(seq 1 60); do' \
      '  if pg_isready -q -h 127.0.0.1 -p 5431 && rabbitmq-diagnostics -q ping >/dev/null 2>&1; then' \
      '    echo "Postgres and RabbitMQ are ready"; exit 0' \
      '  fi' \
      '  sleep 1' \
      'done' \
      'echo "Timed out waiting for Postgres and RabbitMQ" >&2' \
      'exit 1' \
      > /usr/local/bin/hatchet-services \
    && chmod +x /usr/local/bin/hatchet-services

# The server configuration of the CI e2e jobs (.github/workflows/test.yml), for hatchet-server and for anything else
# that boots a server: `set -a; . /src/.env; set +a`. The security check phones home, so it stays off. The cookie
# domain is localhost, so browser-style clients must use http://localhost:8080. The serverless operator refuses to
# start without infra CIDRs or ALLOW_EMPTY_INFRA_CIDRS, which keeps the built-in private-range denylist.
RUN printf '%s\n' \
      'DATABASE_URL=postgresql://hatchet:hatchet@127.0.0.1:5431/hatchet' \
      'SERVER_TLS_CERT_FILE=/src/hack/dev/certs/cluster.pem' \
      'SERVER_TLS_KEY_FILE=/src/hack/dev/certs/cluster.key' \
      'SERVER_TLS_ROOT_CA_FILE=/src/hack/dev/certs/ca.cert' \
      'SERVER_ENCRYPTION_MASTER_KEYSET_FILE=/src/hack/dev/encryption-keys/master.key' \
      'SERVER_ENCRYPTION_JWT_PRIVATE_KEYSET_FILE=/src/hack/dev/encryption-keys/private_ec256.key' \
      'SERVER_ENCRYPTION_JWT_PUBLIC_KEYSET_FILE=/src/hack/dev/encryption-keys/public_ec256.key' \
      'SERVER_PORT=8080' \
      'SERVER_URL=http://localhost:8080' \
      'SERVER_AUTH_COOKIE_SECRETS="kPpegRDNpofgkUsr HoWe67haMOF5qnaB"' \
      'SERVER_AUTH_COOKIE_DOMAIN=localhost' \
      'SERVER_AUTH_COOKIE_INSECURE=true' \
      'SERVER_AUTH_SET_EMAIL_VERIFIED=true' \
      'SERVER_MSGQUEUE_KIND=rabbitmq' \
      'SERVER_MSGQUEUE_RABBITMQ_URL=amqp://user:password@127.0.0.1:5672/' \
      'SERVER_GRPC_INSECURE=true' \
      'SERVER_GRPC_BROADCAST_ADDRESS=127.0.0.1:7070' \
      'SERVER_INTERNAL_CLIENT_BASE_STRATEGY=none' \
      'SERVER_INTERNAL_CLIENT_BASE_INHERIT_BASE=false' \
      'SERVER_SECURITY_CHECK_ENABLED=false' \
      'SERVER_LOGGER_LEVEL=warn' \
      'DATABASE_LOGGER_LEVEL=warn' \
      'SERVER_SERVERLESS_OPERATOR_ENABLED=true' \
      'SERVER_SERVERLESS_OPERATOR_ALLOW_EMPTY_INFRA_CIDRS=true' \
      'SERVER_DEFAULT_TENANT_ENTITLEMENT_SERVERLESS_OPERATOR=true' \
      'SERVER_DEFAULT_TENANT_ENTITLEMENT_DURABLE_STREAMS=true' \
      'SERVER_DEFAULT_TENANT_ENTITLEMENT_DAG_OPERATOR=true' \
      'SERVER_GRPC_OPERATORS_ENABLED=true' \
      'SERVER_OBSERVABILITY_ENABLED=true' \
      > /src/.env

RUN printf '%s\n' \
      '#!/usr/bin/env bash' \
      '# Starts the API (:8080) and the engine (gRPC :7070) in the background, seeds a user and tenant, and writes' \
      '# an API token for that tenant to /tmp/hatchet/token. Logs go to /tmp/hatchet/{api,engine}.log.' \
      'set -euo pipefail' \
      'hatchet-services' \
      'mkdir -p /tmp/hatchet' \
      'cd /src && set -a && . /src/.env && set +a' \
      'hatchet-admin seed > /tmp/hatchet/seed.log 2>&1' \
      'nohup hatchet-engine --no-graceful-shutdown > /tmp/hatchet/engine.log 2>&1 &' \
      'nohup hatchet-api > /tmp/hatchet/api.log 2>&1 &' \
      'for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:8080/api/ready >/dev/null 2>&1 && break; sleep 1; done' \
      'hatchet-admin token create --name scanner --tenant-id 707d0855-80ab-4e1f-a156-f1c4546cbf52 > /tmp/hatchet/token' \
      'echo "API on http://localhost:8080, engine on 127.0.0.1:7070; token in /tmp/hatchet/token"' \
      > /usr/local/bin/hatchet-server \
    && chmod +x /usr/local/bin/hatchet-server

# Quick checks that the image works. A failing test prints a warning and the build carries on. Tests that start
# containers with testcontainers fail without a Docker daemon: those packages are left out, and pkg/repository still
# reports a few. The tests hardcode the "hatchet" database and leave tenants in it, so it is recreated afterwards.
RUN (timeout 1200 go test -vet=off -count=1 \
      $(go list ./... | grep -v -E 'quickstart|pkg/testing/harness|internal/services/ticker|dagoperator/e2e') \
      || echo "WARNING: go unit tests reported failures")
RUN hatchet-services \
    && (DATABASE_URL='postgresql://hatchet:hatchet@127.0.0.1:5431/hatchet?sslmode=disable' \
          timeout 1200 go test -vet=off -count=1 -tags integration \
          $(go list ./... | grep -v -E 'quickstart|pkg/testing/harness|internal/msgqueue/nats') \
        || echo "WARNING: go integration tests reported failures") \
    && su postgres -c "dropdb -p 5431 --force hatchet" \
    && su postgres -c "createdb -p 5431 -O hatchet hatchet" \
    && DATABASE_URL='postgresql://hatchet:hatchet@127.0.0.1:5431/hatchet?sslmode=disable' hatchet-migrate \
    && pg_ctlcluster "$(ls /etc/postgresql | sort -V | tail -n 1)" main stop \
    && (rabbitmqctl stop || true) \
    && rm -rf /var/lib/rabbitmq/mnesia
# The Python tests build a client, which needs a token that parses; nothing connects with it. Jest leaves timers
# open, so --forceExit.
RUN (cd frontend/app && timeout 600 pnpm run test:unit || echo "WARNING: dashboard unit tests reported failures") \
    && (cd sdks/typescript && timeout 600 pnpm run test:unit --forceExit || echo "WARNING: TypeScript SDK unit tests reported failures") \
    && (cd sdks/python \
        && HATCHET_CLIENT_TLS_STRATEGY=none \
           HATCHET_CLIENT_TOKEN=eyJhbGciOiJub25lIn0.eyJncnBjX2Jyb2FkY2FzdF9hZGRyZXNzIjoiMTI3LjAuMC4xOjcwNzAiLCJzZXJ2ZXJfdXJsIjoiaHR0cDovL2xvY2FsaG9zdDo4MDgwIiwic3ViIjoiNzA3ZDA4NTUtODBhYi00ZTFmLWExNTYtZjFjNDU0NmNiZjUyIn0.x \
           timeout 600 poetry run pytest tests/unit \
        || echo "WARNING: Python SDK unit tests reported failures")

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off \
    SERVER_SECURITY_CHECK_ENABLED=false
