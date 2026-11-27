# PostHog build for Anthropic's OSS Scanner.
#
# The scanner uses the repository root as the build context and audits /src with no network. This file
# installs the Python environment, the Node workspace and the Rust crates while the network is available.
# It also builds the Node services and the Rust capture and feature-flags services.
#
# PostgreSQL, Redis, ClickHouse and Redpanda are installed, but nothing starts them. `posthog-test-services
# start` starts the first three for the test suites. `posthog-app start` also runs PostHog itself, with the
# settings of the hobby deploy. threat_model.md says how to use both.

# Versions match the repository: pyproject.toml (Python), .nvmrc (Node), the root Dockerfile (uv),
# docker-compose.base.yml (ClickHouse and Redpanda) and .github/workflows/ci-rust.yml (Rust).
FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM node:26.13.1-bookworm-slim AS node
FROM ghcr.io/posthog/clickhouse-posthog:26.9.5.2-posthog-cf6928b17299 AS clickhouse
FROM docker.io/redpandadata/redpanda:v25.1.9 AS redpanda

# Ubuntu 24.04 is the release that the repository's CI runs the Python and the Node suites on. The Node
# services load a native module that needs its C library version.
FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/src/.venv/bin:/opt/cargo/bin:$PATH

# The build packages from the root Dockerfile and rust/Dockerfile, plus the services that PostHog uses.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        brotli build-essential ca-certificates clang cmake curl git gnupg libclang-dev libffi-dev libpq-dev \
        libsasl2-dev libssl-dev libxml2-dev libxmlsec1 libxmlsec1-dev libxmlsec1-openssl libjemalloc2 \
        libatomic1 libgomp1 media-types pkg-config procps protobuf-compiler python3 tzdata zlib1g-dev \
        postgresql postgresql-contrib redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=clickhouse /usr/bin/clickhouse /usr/bin/clickhouse
COPY --from=redpanda /opt/redpanda /opt/redpanda
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version && clickhouse local --version && /opt/redpanda/bin/rpk version

RUN uv python install 3.14.7

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
        | sh -s -- -y --no-modify-path --profile minimal --default-toolchain 1.91.1 --component rustfmt,clippy \
    && cargo --version

# posthog/conftest.py runs the persons migrations with sqlx-cli. The version is the one in .flox/env/manifest.toml.
RUN cargo install sqlx-cli --version 0.8.3 --locked --no-default-features --features native-tls,postgres \
    && rm -rf /opt/cargo/registry

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# The Python environment with the development group (pytest and the test plugins), from the committed lock
# file, in /src/.venv. lxml and xmlsec build from source against the system libxml2, as in the root Dockerfile.
RUN uv sync --frozen --no-binary-package lxml --no-binary-package xmlsec \
    && rm -rf /root/.cache/uv

# pnpm at the version that package.json pins, then every package of the Node workspace.
RUN npm install -g corepack@0.36.0 && corepack enable && corepack install && pnpm --version
RUN CI=1 HUSKY=0 pnpm install --frozen-lockfile

# The Node services (nodejs/dist) and the native modules that they load, built as in Dockerfile.node.
RUN for package in hogvm-node replay-anonymizer ai-research-v4-native nodejs; do \
        NODE_OPTIONS=--max-old-space-size=8192 bin/turbo --filter="@posthog/$package" build || exit 1; \
    done

# Every crate in rust/Cargo.lock, so that `cargo build --offline` and `cargo test --offline` work. Then debug
# builds of the Rust services that posthog-app starts.
RUN cd rust && cargo fetch --locked \
    && cargo build --locked --bin capture --bin feature-flags --bin personhog-replica --bin personhog-router

# The GeoLite2 database that Django loads for IP geolocation, fetched as in the root Dockerfile.
RUN mkdir -p share \
    && ((curl -fsSL --http1.1 https://mmdbcdn.posthog.net/ | brotli --decompress --output=share/GeoLite2-City.mmdb) \
        && chmod 644 share/GeoLite2-City.mmdb \
        || echo "WARNING: could not fetch the GeoLite2 database")

# Django renders these templates in many API tests. The real files come from a frontend build, which this
# image does not run.
RUN mkdir -p frontend/dist \
    && for page in index layout; do [ -e "frontend/dist/$page.html" ] || touch "frontend/dist/$page.html"; done

# PostgreSQL as in docker-compose.dev.yml: a "posthog" superuser and the "posthog" database.
RUN PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1) \
    && printf '%s\n' \
        "listen_addresses = 'localhost'" \
        'max_connections = 1000' \
        'max_prepared_transactions = 10' \
        'fsync = off' \
        'synchronous_commit = off' \
        'full_page_writes = off' \
        > "/etc/postgresql/$PG_VERSION/main/conf.d/posthog.conf" \
    && pg_ctlcluster "$PG_VERSION" main start \
    && su postgres -c "psql -c \"CREATE USER posthog WITH SUPERUSER PASSWORD 'posthog'\"" \
    && su postgres -c "createdb -O posthog posthog" \
    && pg_ctlcluster "$PG_VERSION" main stop

# ClickHouse Keeper takes the place of ZooKeeper on port 2181. posthog-test-services writes the ClickHouse
# server configuration from docker/clickhouse/ in the checkout each time it starts the server.
RUN mkdir -p /etc/clickhouse-server /etc/clickhouse-keeper /var/lib/clickhouse /var/lib/clickhouse-keeper \
        /var/log/clickhouse-server /var/log/clickhouse-keeper \
    && ln -s /src/posthog/idl /idl \
    && printf '%s\n' \
        '<clickhouse>' \
        '    <logger><level>warning</level><log>/var/log/clickhouse-keeper/keeper.log</log></logger>' \
        '    <listen_host>127.0.0.1</listen_host>' \
        '    <keeper_server>' \
        '        <tcp_port>2181</tcp_port>' \
        '        <server_id>1</server_id>' \
        '        <log_storage_path>/var/lib/clickhouse-keeper/log</log_storage_path>' \
        '        <snapshot_storage_path>/var/lib/clickhouse-keeper/snapshots</snapshot_storage_path>' \
        '        <raft_configuration>' \
        '            <server><id>1</id><hostname>127.0.0.1</hostname><port>9234</port></server>' \
        '        </raft_configuration>' \
        '    </keeper_server>' \
        '</clickhouse>' \
        > /etc/clickhouse-keeper/keeper_config.xml

# The configuration of the development stack names each service by its docker compose host name. The script
# copies the ClickHouse configuration and points those names at the loopback address.
RUN printf '%s\n' \
      '#!/usr/bin/env bash' \
      '# Starts, stops or shows the PostgreSQL, Redis and ClickHouse that PostHog and its tests expect.' \
      '# ClickHouse gets the configuration of the development stack from docker/clickhouse/ in the checkout.' \
      '# Safe to run more than once.' \
      'set -uo pipefail' \
      'PG_VERSION=$(ls /etc/postgresql | sort -V | tail -n 1)' \
      'pg_up() { pg_isready -q -h 127.0.0.1 -p 5432; }' \
      'redis_up() { redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; }' \
      'keeper_up() { [ "$(echo ruok | timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/2181 && cat >&3 && cat <&3" 2>/dev/null)" = imok ]; }' \
      'clickhouse_up() { clickhouse client --host 127.0.0.1 --query "SELECT 1" >/dev/null 2>&1; }' \
      'start() {' \
      '  if ! clickhouse_up; then' \
      '    rm -rf /etc/clickhouse-server/config.xml /etc/clickhouse-server/users.xml /etc/clickhouse-server/config.d' \
      '    mkdir -p /etc/clickhouse-server/config.d' \
      '    cp /src/docker/clickhouse/config.xml /etc/clickhouse-server/config.xml' \
      '    cp /src/docker/clickhouse/users-dev.xml /etc/clickhouse-server/users.xml' \
      '    for name in default dev-memory dev-system-logs dev-idle-polling; do' \
      '      cp "/src/docker/clickhouse/config.d/$name.xml" /etc/clickhouse-server/config.d/' \
      '    done' \
      '    sed -i -E "s#<host>(clickhouse|zookeeper)</host>#<host>127.0.0.1</host>#g; s#kafka:9092#127.0.0.1:9092#g" \' \
      '        /etc/clickhouse-server/config.xml /etc/clickhouse-server/config.d/*.xml' \
      '    # The same files that docker/clickhouse/docker-entrypoint-initdb.d/init-db.sh and the compose volumes provide.' \
      '    cp /src/docker/clickhouse/user_defined_function.xml /etc/clickhouse-server/user_defined_function.xml' \
      '    mkdir -p /var/lib/clickhouse/format_schemas /var/lib/clickhouse/user_scripts' \
      '    cp -r /src/posthog/idl/. /var/lib/clickhouse/format_schemas/' \
      '    cp -r /src/posthog/user_scripts/. /var/lib/clickhouse/user_scripts/' \
      '    rm -f /var/run/clickhouse-server.pid /var/run/clickhouse-keeper.pid' \
      '  fi' \
      '  pg_up || pg_ctlcluster "$PG_VERSION" main start' \
      '  redis_up || redis-server --daemonize yes --save "" --appendonly no --dir /tmp >/dev/null' \
      '  keeper_up || clickhouse keeper --config-file /etc/clickhouse-keeper/keeper_config.xml --daemon \' \
      '      --pid-file /var/run/clickhouse-keeper.pid' \
      '  for _ in $(seq 1 60); do keeper_up && break; sleep 1; done' \
      '  clickhouse_up || (cd /var/lib/clickhouse && clickhouse server --config-file /etc/clickhouse-server/config.xml \' \
      '      --daemon --pid-file /var/run/clickhouse-server.pid)' \
      '  for _ in $(seq 1 120); do' \
      '    if pg_up && redis_up && keeper_up && clickhouse_up; then' \
      '      # Creates the system log tables, such as system.crash_log, that the ClickHouse migrations read.' \
      '      clickhouse client --host 127.0.0.1 --query "SYSTEM FLUSH LOGS"' \
      '      echo "PostgreSQL, Redis and ClickHouse are ready"; return 0' \
      '    fi' \
      '    sleep 1' \
      '  done' \
      '  echo "Timed out. Logs: /var/log/postgresql, /var/log/clickhouse-server, /var/log/clickhouse-keeper" >&2' \
      '  status; return 1' \
      '}' \
      'stop() {' \
      '  for name in server keeper; do' \
      '    pid_file="/var/run/clickhouse-$name.pid"' \
      '    if [ -s "$pid_file" ] && kill "$(cat "$pid_file")" 2>/dev/null; then' \
      '      for _ in $(seq 1 60); do kill -0 "$(cat "$pid_file" 2>/dev/null)" 2>/dev/null || break; sleep 1; done' \
      '    fi' \
      '    rm -f "$pid_file"' \
      '  done' \
      '  redis_up && redis-cli -h 127.0.0.1 shutdown nosave >/dev/null 2>&1' \
      '  pg_up && pg_ctlcluster "$PG_VERSION" main stop' \
      '  return 0' \
      '}' \
      'status() {' \
      '  for name in pg redis keeper clickhouse; do' \
      '    if "${name}_up"; then echo "$name: up"; else echo "$name: down"; fi' \
      '  done' \
      '}' \
      'case "${1:-start}" in' \
      '  start|stop|status) "$1" ;;' \
      '  *) echo "usage: posthog-test-services [start|stop|status]" >&2; exit 2 ;;' \
      'esac' \
      > /usr/local/bin/posthog-test-services \
    && chmod +x /usr/local/bin/posthog-test-services

# PostHog itself, run from the checkout the way the hobby deploy runs it: the settings in .env.services,
# then bin/migrate, bin/docker-server and the other services of docker-compose.hobby.yml. The two keys are random values made for this image.
RUN printf '%s\n' \
      '#!/usr/bin/env bash' \
      '# Runs PostHog from /src with the settings of the hobby deploy (.env.services and docker-compose.hobby.yml).' \
      '# The web server listens on http://localhost:8000. Logs are in /var/log/posthog.' \
      '# The first start applies every database migration, which takes about 30 minutes.' \
      'set -uo pipefail' \
      'cd /src' \
      'mkdir -p /var/log/posthog /var/run/posthog' \
      'SERVICES="kafka personhog flags capture plugins ingestion worker web"' \
      '' \
      'load_env() {' \
      '  unset DEBUG TEST' \
      '  set -a' \
      '  # .env.services names each service by its docker compose host name.' \
      '  source <(sed -E "s#(@|//|=)(db|redis7|clickhouse|kafka|objectstorage)\b#\1localhost#g" /src/.env.services)' \
      '  source /etc/posthog-app.env' \
      '  set +a' \
      '  export DEPLOYMENT=hobby SITE_URL=http://localhost:8000 OTEL_SDK_DISABLED=true OPT_OUT_CAPTURE=true' \
      '  export TEMPORAL_SECRET_KEY="$SECRET_KEY"' \
      '  export PERSONS_DB_WRITER_URL="$DATABASE_URL" PERSONS_DB_READER_URL="$DATABASE_URL"' \
      '  export PERSONS_DATABASE_URL="$DATABASE_URL" BEHAVIORAL_COHORTS_DATABASE_URL="$DATABASE_URL"' \
      '  export CLICKHOUSE_LOGS_CLUSTER_HOST=localhost CLICKHOUSE_LOGS_CLUSTER_SECURE=false' \
      '  export GRANIAN_WORKERS="${GRANIAN_WORKERS:-1}" POSTHOG_GRANIAN_PRELOAD=true WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"' \
      '  export FEATURE_FLAGS_SERVICE_URL=http://localhost:3001 CDP_API_URL=http://localhost:6738' \
      '  export PERSONHOG_ENABLED=true PERSONHOG_ADDR=localhost:50052' \
      '  export CYCLOTRON_NODE_DATABASE_URL=postgres://posthog:posthog@localhost:5432/cyclotron_node' \
      '  # The Node services. Redis takes the place of Valkey.' \
      '  export CDP_REDIS_HOST=localhost CDP_VALKEY_HOST=localhost CDP_VALKEY_PORT=6379' \
      '  export LOGS_REDIS_HOST=localhost LOGS_REDIS_TLS=false TRACES_REDIS_HOST=localhost TRACES_REDIS_TLS=false' \
      '  export COOKIELESS_REDIS_HOST=localhost COOKIELESS_REDIS_PORT=6379 KAFKA_CONSUMER_FETCH_WAIT_MAX_MS=1000' \
      '  # The Node services default each Kafka client to the compose host name kafka:9092.' \
      '  local slot' \
      '  for slot in KAFKA_CONSUMER CDP_INTERNAL_EVENTS_CONSUMER KAFKA_INGESTION_UPSTREAM_PRODUCER \' \
      '      KAFKA_INGESTION_DOWNSTREAM_PRODUCER KAFKA_INGESTION_SESSIONREPLAY_PRODUCER KAFKA_MSK_CDP_INTAKE_PRODUCER \' \
      '      KAFKA_WAREHOUSE_PRODUCER KAFKA_WARPSTREAM_CYCLOTRON_PRODUCER KAFKA_WARPSTREAM_INGESTION_PRODUCER \' \
      '      KAFKA_WARPSTREAM_LOGS_PRODUCER KAFKA_WARPSTREAM_METRICS_PRODUCER KAFKA_PRODUCER; do' \
      '    export "${slot}_METADATA_BROKER_LIST=localhost:9092"' \
      '  done' \
      '  grep -q " kafka$" /etc/hosts 2>/dev/null || echo "127.0.0.1 kafka" >> /etc/hosts 2>/dev/null || true' \
      '}' \
      'running() { [ -s "/var/run/posthog/$1.pid" ] && kill -0 "$(cat "/var/run/posthog/$1.pid")" 2>/dev/null; }' \
      'answers() { curl -fs -o /dev/null --max-time 5 "$1"; }' \
      'wait_for() {' \
      '  local name=$1 url=$2' \
      '  for _ in $(seq 1 "${3:-90}"); do' \
      '    answers "$url" && return 0' \
      '    running "$name" || break' \
      '    sleep 2' \
      '  done' \
      '  echo "$name did not start. See /var/log/posthog/$name.log" >&2' \
      '  tail -n 20 "/var/log/posthog/$name.log" >&2' \
      '  return 1' \
      '}' \
      'launch() {' \
      '  local name=$1; shift' \
      '  running "$name" && return 0' \
      '  setsid "$@" >> "/var/log/posthog/$name.log" 2>&1 < /dev/null &' \
      '  echo $! > "/var/run/posthog/$name.pid"' \
      '}' \
      '' \
      'start_kafka() {' \
      '  mkdir -p /var/lib/redpanda/data /etc/redpanda' \
      '  launch kafka /opt/redpanda/bin/rpk redpanda start --mode dev-container --smp 1 --memory 1G --reserve-memory 0M \' \
      '      --overprovisioned --kafka-addr 127.0.0.1:9092 --advertise-kafka-addr 127.0.0.1:9092 \' \
      '      --rpc-addr 127.0.0.1:33145 --advertise-rpc-addr 127.0.0.1:33145 --set redpanda.auto_create_topics_enabled=true' \
      '  wait_for kafka http://127.0.0.1:9644/v1/status/ready || return 1' \
      '  # The Node services verify their topics at start, as kafka-init does in the hobby deploy.' \
      '  grep -vE "^[[:space:]]*(#|$)" docker/kafka/topics.txt \' \
      '      | xargs /opt/redpanda/bin/rpk topic create --brokers 127.0.0.1:9092 -p 1 -r 1 >> /var/log/posthog/kafka.log 2>&1' \
      '  return 0' \
      '}' \
      'start_personhog() {' \
      '  launch personhog-replica env GRPC_ADDRESS=0.0.0.0:50051 PRIMARY_DATABASE_URL="$DATABASE_URL" METRICS_PORT=9100 \' \
      '      RUST_LOG=info rust/target/debug/personhog-replica' \
      '  launch personhog env GRPC_ADDRESS=0.0.0.0:50052 REPLICA_URL=http://localhost:50051 BACKEND_TIMEOUT_MS=5000 \' \
      '      METRICS_PORT=9101 RUST_LOG=info rust/target/debug/personhog-router' \
      '  wait_for personhog http://localhost:9101/_readiness' \
      '}' \
      'start_flags() {' \
      '  launch flags env ADDRESS=0.0.0.0:3001 RUST_LOG=info MAXMIND_DB_PATH=/src/share/GeoLite2-City.mmdb \' \
      '      WRITE_DATABASE_URL="$DATABASE_URL" READ_DATABASE_URL="$DATABASE_URL" \' \
      '      PERSONS_WRITE_DATABASE_URL="$DATABASE_URL" PERSONS_READ_DATABASE_URL="$DATABASE_URL" \' \
      '      rust/target/debug/feature-flags' \
      '  wait_for flags http://localhost:3001/_readiness' \
      '}' \
      'start_capture() {' \
      '  launch capture env ADDRESS=0.0.0.0:3000 CAPTURE_MODE=events RUST_LOG=info,rdkafka=warn \' \
      '      KAFKA_TOPIC=events_plugin_ingestion CAPTURE_OUTPUT_ANALYTICS_MAIN_TOPIC=events_plugin_ingestion \' \
      '      KAFKA_ERROR_TRACKING_TOPIC=ingestion-errortracking-main \' \
      '      CAPTURE_OUTPUT_ERROR_TRACKING_TOPIC=ingestion-errortracking-main \' \
      '      KAFKA_INGESTION_PRODUCER_METADATA_BROKER_LIST=localhost:9092 \' \
      '      rust/target/debug/capture' \
      '  wait_for capture http://localhost:3000/_readiness' \
      '}' \
      'start_plugins() {' \
      '  # bin/migrate skips this database in a hobby deploy, and the CDP job queue needs it.' \
      '  ./rust/bin/migrate-cyclotron-node >> /var/log/posthog/plugins.log 2>&1 || return 1' \
      '  launch plugins node nodejs/dist/index.js' \
      '  wait_for plugins http://localhost:6738/_health' \
      '}' \
      'start_ingestion() {' \
      '  launch ingestion env PLUGIN_SERVER_MODE=ingestion-v2-combined HTTP_SERVER_PORT=6739 node nodejs/dist/index.js' \
      '  wait_for ingestion http://localhost:6739/_health' \
      '}' \
      'start_worker() { launch worker ./bin/docker-worker-celery --with-embedded-scheduler; }' \
      'start_web() {' \
      '  launch web ./bin/docker-server' \
      '  wait_for web http://localhost:8000/_health 180 && echo "PostHog is ready at http://localhost:8000"' \
      '}' \
      '' \
      'migrate() { posthog-test-services start && load_env && ./bin/migrate; }' \
      'start() {' \
      '  local wanted=" personhog web $* "' \
      '  [ "${1:-}" = "--all" ] && wanted=" $SERVICES "' \
      '  case "$wanted" in *" capture "*|*" plugins "*|*" ingestion "*) wanted="$wanted kafka " ;; esac' \
      '  for name in $wanted; do' \
      '    case " $SERVICES " in *" $name "*) ;; *) echo "unknown service: $name (services: $SERVICES)" >&2; return 2 ;; esac' \
      '  done' \
      '  posthog-test-services start || return 1' \
      '  load_env' \
      '  if ! ./bin/migrate-check > /dev/null 2>&1; then' \
      '    echo "Applying the database migrations. Log: /var/log/posthog/migrate.log"' \
      '    ./bin/migrate > /var/log/posthog/migrate.log 2>&1 || { tail -n 20 /var/log/posthog/migrate.log >&2; return 1; }' \
      '  fi' \
      '  local failed=0' \
      '  for name in $SERVICES; do' \
      '    case "$wanted" in *" $name "*) "start_$name" || failed=1 ;; esac' \
      '  done' \
      '  return "$failed"' \
      '}' \
      'stop() {' \
      '  for name in web worker ingestion plugins capture flags personhog personhog-replica kafka; do' \
      '    running "$name" && kill -TERM -- "-$(cat "/var/run/posthog/$name.pid")" 2>/dev/null' \
      '    rm -f "/var/run/posthog/$name.pid"' \
      '  done' \
      '  return 0' \
      '}' \
      'status() {' \
      '  for name in $SERVICES; do' \
      '    if running "$name"; then echo "$name: up"; else echo "$name: down"; fi' \
      '  done' \
      '}' \
      '# Creates a user, an organization, a project and a personal API key with bin/hobby-ci-setup-user.py.' \
      'user() { load_env && PYTHONPATH=/src python bin/hobby-ci-setup-user.py; }' \
      '# Runs any command with the settings of the app, for example: posthog-app run python manage.py shell' \
      'run() { load_env && "$@"; }' \
      '' \
      'command=${1:-start}' \
      'case "$command" in' \
      '  start|stop|status|migrate|user|run) shift || true; "$command" "$@" ;;' \
      '  *) echo "usage: posthog-app [start [--all|service...]|stop|status|migrate|user|run <command>]" >&2; exit 2 ;;' \
      'esac' \
      > /usr/local/bin/posthog-app \
    && chmod +x /usr/local/bin/posthog-app
RUN printf 'SECRET_KEY=%s\nENCRYPTION_SALT_KEYS=%s\n' \
        "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" "$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')" \
        > /etc/posthog-app.env

# The network is gone after this point. The package managers must use what the steps above fetched.
# The service settings replace the docker compose host names that the repository uses by default.
ENV UV_PYTHON_DOWNLOADS=never \
    PGHOST=localhost \
    CLICKHOUSE_HOST=localhost \
    REDIS_URL=redis://localhost:6379/ \
    KAFKA_HOSTS=localhost:9092 \
    UV_OFFLINE=1 \
    UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    VIRTUAL_ENV=/src/.venv \
    COREPACK_ENABLE_NETWORK=0 \
    CARGO_NET_OFFLINE=true
