# syntax=docker/dockerfile:1.7
# Keep sources, toolchains, dependencies, and test services in the final image.
FROM golang:1.25-alpine

RUN apk add --no-cache \
    bash build-base ca-certificates curl ffmpeg git jq nodejs npm openssl \
    postgresql17 postgresql17-client postgresql17-contrib python3 redis

WORKDIR /src
COPY go.mod go.sum ./
# Do not use cache mounts: the offline agent needs these files in the image.
RUN go mod download
COPY . /src

RUN cd cmd/telesrv-admin/web && npm ci --no-audit --no-fund && npm run build
RUN cd cmd/bots/grammystore && npm ci --no-audit --no-fund

ENV GOMAXPROCS=2
RUN mkdir -p /opt/gramsrv/bin && \
    go build -p 2 -o /opt/gramsrv/bin/ \
      ./cmd/telesrv ./cmd/telesrv-admin ./cmd/telesrv-load
# Compile the remaining packages and tests while dependency downloads are allowed.
RUN go test -p 2 ./... -run '^$' -timeout 5m

# Start disposable services inside the scanner's network-isolated container.
# These credentials and data are local test fixtures, never deployment settings.
RUN <<'SETUP'
cat > /usr/local/bin/gramsrv-test-services <<'SCRIPT'
#!/bin/sh
set -eu
install -d -o postgres -g postgres -m 0700 /tmp/gramsrv-audit-pg
if [ ! -f /tmp/gramsrv-audit-pg/PG_VERSION ]; then
  su postgres -s /bin/sh -c 'initdb -D /tmp/gramsrv-audit-pg --auth=trust --encoding=UTF8 --locale=C' >/tmp/gramsrv-audit-initdb.log
fi
if ! su postgres -s /bin/sh -c 'pg_ctl -D /tmp/gramsrv-audit-pg status' >/dev/null 2>&1; then
  su postgres -s /bin/sh -c 'pg_ctl -D /tmp/gramsrv-audit-pg -l /tmp/gramsrv-audit-pg/server.log -o "-h 127.0.0.1 -p 5432 -k /tmp" -w start'
fi
if [ "$(psql -h 127.0.0.1 -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='gramsrv_test'")" != 1 ]; then
  createdb -h 127.0.0.1 -U postgres gramsrv_test
fi
if ! redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; then
  redis-server --bind 127.0.0.1 --port 6379 --save '' --appendonly no --daemonize yes --logfile /tmp/gramsrv-audit-redis.log
fi
pg_isready -h 127.0.0.1 -U postgres -d gramsrv_test
redis-cli -h 127.0.0.1 -p 6379 ping
SCRIPT
chmod 0755 /usr/local/bin/gramsrv-test-services
SETUP

ENV PATH="/opt/gramsrv/bin:${PATH}" \
    GOPROXY=off \
    GOSUMDB=off
CMD ["bash"]
