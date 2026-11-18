# syntax=docker/dockerfile:1
FROM node:24-trixie-slim AS node
FROM ruby:4.0.5-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    RAILS_ENV=test \
    DATABASE_URL=postgresql://postgres:scanner-test@127.0.0.1/loomio_test \
    SECRET_KEY_BASE=oss-scanner-test-only-secret-key-base-0123456789abcdef0123456789abcdef \
    CANONICAL_HOST=localhost \
    NODE_OPTIONS=--max-old-space-size=2048

# All dependencies are fetched during the online build; PostgreSQL runs locally
# in the finished image so reproductions and Rails tests work without a network.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git libyaml-dev libpq-dev \
      postgresql-17 libvips imagemagick ffmpeg poppler-utils \
      python3 bash procps netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY . /src
WORKDIR /src
RUN npm install --global "npm@$(cat .npm-version)" --no-audit --no-fund \
    && bundle install
RUN cd vue && npm ci --no-audit --no-fund && npm run build
RUN cd hocuspocus && npm ci --no-audit --no-fund
RUN cd haraka && npm ci --no-audit --no-fund
RUN cd push-relay && npm ci --no-audit --no-fund

# The repository deliberately does not ship a local database.yml.
RUN cp config/database.yml.postgresql config/database.yml \
    && pg_ctlcluster 17 main start \
    && runuser -u postgres -- psql -c "ALTER USER postgres PASSWORD 'scanner-test'" \
    && bin/rails db:prepare \
    && pg_ctlcluster 17 main stop

# ImageMagick uses this delegate to render the SVG pie charts exercised by tests.
RUN apt-get update && apt-get install -y --no-install-recommends librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

# The scanner opens a shell rather than invoking an entrypoint. This helper
# starts the local database before running tests or another reproduction command.
RUN <<'SETUP'
cat > /usr/local/bin/loomio-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
if ! pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
  pg_ctlcluster 17 main start
fi
bin/rails db:prepare
if [ "$#" -eq 0 ]; then
  set -- bin/rails test
fi
exec "$@"
SCRIPT
chmod +x /usr/local/bin/loomio-test
SETUP

CMD ["bash"]
