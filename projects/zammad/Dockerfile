# Zammad test environment: Ruby on Rails backend with PostgreSQL, Redis and Elasticsearch inside the image, so
# that the RSpec suite runs without network access. Start the services with `zammad-services` first.
ARG NODE_VERSION=24

FROM docker.io/library/node:${NODE_VERSION}-trixie-slim AS node
RUN npm -g install corepack && corepack enable pnpm

FROM docker.io/library/debian:trixie-slim

SHELL ["/bin/bash", "-o", "errexit", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    RAILS_ENV=test \
    Z_LOCALES=en-us:de-de \
    TZ=Europe/London \
    REDIS_URL=redis://localhost:6379 \
    ES_URL=http://127.0.0.1:9200 \
    ES_INDEX=estest.scanner_zammad \
    ES_PATH_CONF=/etc/elasticsearch \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends \
      autoconf bison build-essential ca-certificates curl git gnupg libffi-dev libgmp-dev libimlib2 \
      libimlib2-dev libjemalloc2 libpq-dev libreadline-dev libssl-dev libyaml-dev postgresql \
      postgresql-contrib redis-server shared-mime-info zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Elasticsearch for search and overviews, single node without security, bound to loopback.
RUN curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor -o /usr/share/keyrings/elastic.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/elastic.gpg] https://artifacts.elastic.co/packages/9.x/apt stable main" \
      > /etc/apt/sources.list.d/elastic.list \
    && apt-get update -qq \
    && apt-get install -y --no-install-recommends elasticsearch \
    && rm -rf /var/lib/apt/lists/* \
    && printf '%s\n' 'cluster.name: zammad' 'network.host: 127.0.0.1' 'discovery.type: single-node' \
      'xpack.security.enabled: false' 'cluster.routing.allocation.disk.threshold_enabled: false' \
      'path.data: /var/lib/elasticsearch' 'path.logs: /var/log/elasticsearch' \
      > /etc/elasticsearch/elasticsearch.yml \
    && printf '%s\n' '-Xms1g' '-Xmx1g' > /etc/elasticsearch/jvm.options.d/heap.options \
    && rm /etc/elasticsearch/elasticsearch.keystore \
    && /usr/share/elasticsearch/bin/elasticsearch-keystore create \
    && chown root:elasticsearch /etc/elasticsearch/elasticsearch.keystore \
    && chmod 660 /etc/elasticsearch/elasticsearch.keystore

# Builds the Ruby version that the checkout pins, so Ruby updates in Zammad need no change here.
COPY .ruby-version /tmp/.ruby-version
RUN git clone --depth 1 https://github.com/rbenv/ruby-build.git /tmp/ruby-build \
    && MAKE_OPTS="-j$(nproc)" /tmp/ruby-build/bin/ruby-build "$(cat /tmp/.ruby-version)" /usr/local \
    && rm -rf /tmp/ruby-build /tmp/.ruby-version \
    && ruby --version

COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node /usr/local/bin /usr/local/bin

# Starts PostgreSQL, Redis and Elasticsearch; the scanner runs no init system. Elasticsearch needs a resolvable
# hostname, which offline containers lack, and starts empty because Lucene locks copied between layers break.
RUN printf '%s\n' '#!/bin/bash' 'set -e' \
      'pg_ctlcluster "$(ls /usr/lib/postgresql)" main status >/dev/null 2>&1 || pg_ctlcluster "$(ls /usr/lib/postgresql)" main start' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes --save "" --appendonly no' \
      'until redis-cli ping >/dev/null 2>&1; do sleep 0.2; done' \
      'getent hosts "$(hostname)" >/dev/null || echo "127.0.0.1 $(hostname)" >> /etc/hosts' \
      'curl -s "$ES_URL" >/dev/null || { find /var/lib/elasticsearch -mindepth 1 -delete; su elasticsearch -s /bin/bash -c "ES_PATH_CONF=$ES_PATH_CONF /usr/share/elasticsearch/bin/elasticsearch -d -p /tmp/elasticsearch.pid"; }' \
      'for i in $(seq 120); do curl -sf "$ES_URL/_cluster/health?wait_for_status=yellow" >/dev/null && exit 0; sleep 1; done' \
      'echo "Elasticsearch did not start, see /var/log/elasticsearch/" >&2; exit 1' \
      > /usr/local/bin/zammad-services \
    && chmod +x /usr/local/bin/zammad-services \
    && zammad-services \
    && su postgres -c "createuser --superuser root"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN bundle install -j"$(nproc)" \
    && pnpm install --frozen-lockfile \
    && cp config/database/database.yml config/database.yml

RUN zammad-services \
    && bundle exec rake zammad:db:init \
    && bundle exec rake assets:precompile

# A quick smoke test so the image is known to work; failures do not abort the build.
RUN zammad-services \
    && (bundle exec rspec spec/models/ticket_spec.rb || echo "WARNING: rspec smoke test reported failures")
