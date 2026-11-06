# Zammad test environment: Ruby on Rails backend with PostgreSQL and Redis inside the image, so that
# the RSpec suite runs without network access. Start the services with `zammad-services` first.
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
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends \
      autoconf bison build-essential ca-certificates curl git gnupg libffi-dev libgmp-dev libimlib2 \
      libimlib2-dev libjemalloc2 libpq-dev libreadline-dev libssl-dev libyaml-dev postgresql \
      postgresql-contrib redis-server shared-mime-info zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Builds the Ruby version that the checkout pins, so Ruby updates in Zammad need no change here.
COPY .ruby-version /tmp/.ruby-version
RUN git clone --depth 1 https://github.com/rbenv/ruby-build.git /tmp/ruby-build \
    && MAKE_OPTS="-j$(nproc)" /tmp/ruby-build/bin/ruby-build "$(cat /tmp/.ruby-version)" /usr/local \
    && rm -rf /tmp/ruby-build /tmp/.ruby-version \
    && ruby --version

COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node /usr/local/bin /usr/local/bin

# Starts PostgreSQL and Redis; the scanner runs no init system.
RUN printf '%s\n' '#!/bin/bash' 'set -e' \
      'pg_ctlcluster "$(ls /usr/lib/postgresql)" main status >/dev/null 2>&1 || pg_ctlcluster "$(ls /usr/lib/postgresql)" main start' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes --save "" --appendonly no' \
      'until redis-cli ping >/dev/null 2>&1; do sleep 0.2; done' \
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
    && (bundle exec rspec spec/models/ticket_spec.rb --tag ~searchindex || echo "WARNING: rspec smoke test reported failures")
