# Onetime Secret: OSS Scanner build.
#
# The toolchain mirrors docker/base.dockerfile (Ruby from .ruby-version, Node 26, pnpm from package.json). The test
# services in compose.test.yml (Valkey, RabbitMQ) are installed as packages, because the scan VM has no Docker and
# no network. `ots-test-services` starts them on the same 127.0.0.1 ports the test lanes expect.
FROM docker.io/library/node:26-trixie-slim AS node
FROM docker.io/library/ruby:3.4.10-slim-trixie

# CI=true makes tests/lanes/run use datastore index 0 and skip the per-worktree RabbitMQ vhost, as in GitHub CI.
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    BUNDLE_FROZEN=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libssl-dev libffi-dev libyaml-dev libsqlite3-dev libpq-dev pkg-config \
      libsodium23 git curl ca-certificates python3 procps \
      valkey-server rabbitmq-server \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version

# Test services on the compose.test.yml ports: valkey 2163, rabbitmq 2156 (guest/guest, loopback only).
RUN printf '%s\n' 'NODENAME=rabbit@localhost' 'NODE_IP_ADDRESS=127.0.0.1' 'NODE_PORT=2156' \
      > /etc/rabbitmq/rabbitmq-env.conf \
    && printf '%s\n' \
      '#!/bin/bash' \
      '# Start the compose.test.yml services for tests/lanes/run. Safe to run more than once.' \
      'set -e' \
      'if ! valkey-cli -p 2163 ping >/dev/null 2>&1; then' \
      '  valkey-server --bind 127.0.0.1 --port 2163 --save "" --appendonly no --databases 65536 \' \
      '    --daemonize yes --logfile /var/log/valkey-test.log' \
      'fi' \
      'if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then' \
      '  rabbitmq-server >/var/log/rabbitmq-test.log 2>&1 &' \
      '  for _ in $(seq 60); do rabbitmq-diagnostics -q ping >/dev/null 2>&1 && break; sleep 1; done' \
      '  rabbitmqctl -q await_startup' \
      'fi' \
      'echo "test services up: valkey 127.0.0.1:2163, rabbitmq 127.0.0.1:2156"' \
      > /usr/local/bin/ots-test-services \
    && chmod +x /usr/local/bin/ots-test-services

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm install -g "$(node -p 'require("./package.json").packageManager')" && pnpm --version
# tests/lanes/run clears every variable except PATH, HOME and a few CI flags, which drops the ruby image's GEM_HOME and
# BUNDLE_APP_CONFIG. Install into Ruby's default gem directory so the gems resolve with or without them.
RUN env -u GEM_HOME -u BUNDLE_APP_CONFIG bundle install --jobs "$(nproc)" --retry 3
RUN pnpm install --frozen-lockfile && pnpm run build

# Run the unit lane so the image is known to work; a failing test does not fail the build.
RUN ots-test-services \
    && (timeout 1200 tests/lanes/run unit || echo "WARNING: tests/lanes/run unit reported failures") \
    && rabbitmqctl -q stop \
    && (valkey-cli -p 2163 shutdown nosave || true)
