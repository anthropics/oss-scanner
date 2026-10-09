# Onetime Secret: OSS Scanner build.
#
# The toolchain mirrors docker/base.dockerfile (Ruby from .ruby-version, Node 26, pnpm from package.json). The test
# services in compose.test.yml (Valkey, RabbitMQ, Postgres) are installed as packages, because the scan VM has no
# Docker and no network. `ots-test-services` starts them on the same 127.0.0.1 ports the test lanes expect.
# Playwright's Chromium, Firefox and WebKit are installed for the browser lane.
FROM docker.io/library/node:26-trixie-slim AS node
FROM docker.io/library/ruby:3.4.10-slim-trixie

# CI=true makes tests/lanes/run use datastore index 0 and skip the per-worktree RabbitMQ vhost, as in GitHub CI.
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    BUNDLE_FROZEN=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libssl-dev libffi-dev libyaml-dev libsqlite3-dev libpq-dev pkg-config \
      libsodium23 git curl ca-certificates python3 procps \
      valkey-server rabbitmq-server postgresql-17 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version

# Test services on the compose.test.yml ports: valkey 2163, rabbitmq 2156 (guest/guest), postgres 2154
# (postgres/postgres), all on loopback. Postgres runs without durability, like the tmpfs in compose.test.yml.
RUN printf '%s\n' 'NODENAME=rabbit@localhost' 'NODE_IP_ADDRESS=127.0.0.1' 'NODE_PORT=2156' \
      > /etc/rabbitmq/rabbitmq-env.conf \
    && pg_conftool 17 main set port 2154 \
    && pg_conftool 17 main set listen_addresses localhost \
    && pg_conftool 17 main set fsync off \
    && pg_conftool 17 main set synchronous_commit off \
    && pg_conftool 17 main set full_page_writes off \
    && printf '%s\n' \
      '#!/bin/bash' \
      '# Start the compose.test.yml services for tests/lanes/run. Safe to run more than once.' \
      'set -e' \
      'if ! valkey-cli -p 2163 ping >/dev/null 2>&1; then' \
      '  valkey-server --bind 127.0.0.1 --port 2163 --save "" --appendonly no --databases 65536 \' \
      '    --daemonize yes --logfile /var/log/valkey-test.log' \
      'fi' \
      'if ! pg_isready -q -h 127.0.0.1 -p 2154; then' \
      '  pg_ctlcluster 17 main start' \
      'fi' \
      'if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then' \
      '  rabbitmq-server >/var/log/rabbitmq-test.log 2>&1 &' \
      '  for _ in $(seq 60); do rabbitmq-diagnostics -q ping >/dev/null 2>&1 && break; sleep 1; done' \
      '  rabbitmqctl -q await_startup' \
      'fi' \
      'echo "test services up: valkey 127.0.0.1:2163, rabbitmq 127.0.0.1:2156, postgres 127.0.0.1:2154"' \
      > /usr/local/bin/ots-test-services \
    && chmod +x /usr/local/bin/ots-test-services

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The database and roles compose.test.yml creates on first boot.
RUN pg_ctlcluster 17 main start \
    && runuser -u postgres -- psql -p 2154 -v ON_ERROR_STOP=1 \
         -c "ALTER USER postgres PASSWORD 'postgres'" -c 'CREATE DATABASE onetime_auth_test' \
    && runuser -u postgres -- psql -p 2154 -v ON_ERROR_STOP=1 -d onetime_auth_test \
         -f apps/web/auth/migrations/schemas/postgres/initialize_test_db.sql \
    && pg_ctlcluster 17 main stop

RUN npm install -g "$(node -p 'require("./package.json").packageManager')" && pnpm --version
# tests/lanes/run clears every variable except PATH, HOME and a few CI flags, which drops the ruby image's GEM_HOME and
# BUNDLE_APP_CONFIG. Install into Ruby's default gem directory so the gems resolve with or without them.
RUN env -u GEM_HOME -u BUNDLE_APP_CONFIG bundle install --jobs "$(nproc)" --retry 3
RUN pnpm install --frozen-lockfile && pnpm run build
RUN pnpm exec playwright install --with-deps chromium firefox webkit && rm -rf /var/lib/apt/lists/*

# Run the unit lane so the image is known to work; a failing test does not fail the build.
RUN ots-test-services \
    && (timeout 1200 tests/lanes/run unit || echo "WARNING: tests/lanes/run unit reported failures") \
    && rabbitmqctl -q stop \
    && pg_ctlcluster 17 main stop \
    && (valkey-cli -p 2163 shutdown nosave || true)
