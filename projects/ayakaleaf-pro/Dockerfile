# Ayakaleaf Pro: a self-hosted Overleaf (Community Edition based) with extra modules under services/web/modules/.
#
# One image holds the whole stack, built from the repository's own server-ce/Dockerfile-base and
# server-ce/Dockerfile (the published sharelatex/sharelatex-base image is stale, so it is not used). MongoDB and
# Redis, which docker-compose.yml runs as separate containers, are installed here and listen on 127.0.0.1.
#
#   ayakaleaf-test-services   start MongoDB (replica set "overleaf") and Redis; safe to run again
#   ayakaleaf-start           also start every Overleaf service; the site is then on http://127.0.0.1/
#
# The source is at /overleaf (where the services expect it); /src links to it.
FROM phusion/baseimage:noble-1.0.3

ENV TEXMFVAR=/var/lib/overleaf/tmp/texmf-var

# --- server-ce/Dockerfile-base: system packages and Node.js 24 ---
RUN apt-get update \
&&  apt-get install -y \
      unattended-upgrades \
      build-essential wget net-tools unzip time poppler-utils optipng strace nginx git python3 python-is-python3 zlib1g-dev libpcre3-dev gettext-base libwww-perl ca-certificates curl gnupg \
      qpdf \
&&  unattended-upgrade --verbose --no-minimal-upgrade-steps \
&&  mkdir -p /etc/apt/keyrings \
&&  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
&&  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
&&  apt-get update \
&&  apt-get install -y nodejs \
&&  rm -rf /etc/nginx/nginx.conf /etc/nginx/sites-enabled/default

# --- MongoDB 8.0 and Redis, in place of the mongo and redis containers of docker-compose.yml ---
RUN curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | gpg --dearmor -o /etc/apt/keyrings/mongodb-server-8.0.gpg \
&&  echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-8.0.list \
&&  apt-get update \
&&  apt-get install -y mongodb-org redis-server \
&&  rm -rf /var/lib/apt/lists/*

# --- server-ce/Dockerfile-base: TeX Live (scheme-basic, as in the base image) ---
ARG TEXLIVE_MIRROR=https://mirror.ox.ac.uk/sites/ctan.org/systems/texlive/tlnet
RUN mkdir /install-tl-unx \
&&  wget --quiet https://tug.org/texlive/files/texlive.asc \
&&  gpg --import texlive.asc \
&&  rm texlive.asc \
&&  wget --quiet ${TEXLIVE_MIRROR}/install-tl-unx.tar.gz \
&&  wget --quiet ${TEXLIVE_MIRROR}/install-tl-unx.tar.gz.sha512 \
&&  wget --quiet ${TEXLIVE_MIRROR}/install-tl-unx.tar.gz.sha512.asc \
&&  gpg --verify install-tl-unx.tar.gz.sha512.asc \
&&  sha512sum -c install-tl-unx.tar.gz.sha512 \
&&  tar -xz -C /install-tl-unx --strip-components=1 -f install-tl-unx.tar.gz \
&&  rm install-tl-unx.tar.gz* \
&&  echo "tlpdbopt_autobackup 0" >> /install-tl-unx/texlive.profile \
&&  echo "tlpdbopt_install_docfiles 0" >> /install-tl-unx/texlive.profile \
&&  echo "tlpdbopt_install_srcfiles 0" >> /install-tl-unx/texlive.profile \
&&  echo "selected_scheme scheme-basic" >> /install-tl-unx/texlive.profile \
&&  /install-tl-unx/install-tl -profile /install-tl-unx/texlive.profile -repository ${TEXLIVE_MIRROR} \
&&  $(find /usr/local/texlive -name tlmgr) path add \
&&  tlmgr install --repository ${TEXLIVE_MIRROR} latexmk texcount synctex etoolbox xetex \
&&  tlmgr path add \
&&  rm -rf /install-tl-unx

RUN adduser --system --group --home /overleaf --no-create-home overleaf \
&&  mkdir -p /var/lib/overleaf/data/template_files /var/log/overleaf \
&&  chown -R www-data:www-data /var/lib/overleaf /var/log/overleaf

# --- server-ce/Dockerfile: install and compile, keeping development dependencies for the tests ---
ENV COREPACK_HOME=/opt/corepack
RUN corepack enable && corepack install -g yarn@4.18.0

COPY . /overleaf
WORKDIR /overleaf
RUN ln -s /overleaf /src

# Node's default heap is too small for webpack on this codebase.
ENV NODE_OPTIONS=--max-old-space-size=16384 \
    CYPRESS_INSTALL_BINARY=0
RUN yarn install
RUN cd services/web \
&&  yarn run precompile-pug \
&&  yarn run extract-translations \
&&  yarn run webpack:production \
&&  yarn run pyodide:fetch
ENV COREPACK_ENABLE_NETWORK=0 \
    NODE_OPTIONS="--require /overleaf/.pnp.cjs --import /overleaf/.pnp.register.mjs"

# --- server-ce/Dockerfile: runit services, nginx, cron, init scripts, settings ---
RUN cp -r server-ce/runit/. /etc/service/ \
&&  mkdir -p /etc/overleaf /etc/nginx/templates /etc/my_init.pre_shutdown.d /overleaf/bin /usr/local/share/latexmk \
&&  cp server-ce/config/env.sh server-ce/config/settings.js /etc/overleaf/ \
&&  cp server-ce/nginx/nginx.conf.template /etc/nginx/templates/ \
&&  cp server-ce/nginx/overleaf.conf server-ce/nginx/clsi-nginx.conf /etc/nginx/sites-enabled/ \
&&  cp server-ce/logrotate/overleaf /etc/logrotate.d/overleaf && chmod 644 /etc/logrotate.d/overleaf \
&&  cp server-ce/config/crontab-history server-ce/config/crontab-deletion /etc/cron.d/ \
&&  chmod 600 /etc/cron.d/crontab-history /etc/cron.d/crontab-deletion \
&&  cp -r server-ce/init_scripts/. /etc/my_init.d/ \
&&  cp -r server-ce/init_preshutdown_scripts/. /etc/my_init.pre_shutdown.d/ \
&&  cp server-ce/config/production.json server-ce/config/custom-environment-variables.json services/history-v1/config/ \
&&  install -m 755 server-ce/bin/grunt /usr/local/bin/grunt \
&&  install -m 755 server-ce/bin/flush-history-queues server-ce/bin/force-history-resyncs /overleaf/bin/ \
&&  cp server-ce/config/latexmkrc /usr/local/share/latexmk/LatexMk

# MongoDB and Redis are on 127.0.0.1, so no "dockerhost" entry is needed; writing it fails during docker build
# (/etc/hosts is read-only there), and a failing init script makes my_init kill every process.
RUN rm /etc/my_init.d/100_set_docker_host_ipaddress.sh

# Local-only settings for reproductions; no production credentials are needed.
ENV OVERLEAF_CONFIG=/etc/overleaf/settings.js \
    SITE_MAINTENANCE_FILE=/etc/overleaf/site_status \
    WEB_API_USER=overleaf \
    ADMIN_PRIVILEGE_AVAILABLE=true \
    OVERLEAF_APP_NAME="Ayakaleaf Pro" \
    OPTIMISE_PDF=true \
    REQ_VALIDATION_MODE=enforce-log \
    KILL_PROCESS_TIMEOUT=55 \
    KILL_ALL_PROCESSES_TIMEOUT=55 \
    GRACEFUL_SHUTDOWN_DELAY_SECONDS=1 \
    NODE_ENV=production \
    LOG_LEVEL=info \
    OVERLEAF_MONGO_URL=mongodb://127.0.0.1/sharelatex \
    OVERLEAF_REDIS_HOST=127.0.0.1 \
    REDIS_HOST=127.0.0.1 \
    OVERLEAF_INVITE_TOKEN_SECRET=oss-scanner-local-only-not-a-production-secret \
    ENABLED_LINKED_FILE_TYPES=project_file,project_output_file \
    EMAIL_CONFIRMATION_DISABLED=true
RUN touch $SITE_MAINTENANCE_FILE

# Nothing starts MongoDB or Redis on its own: run ayakaleaf-test-services (databases only) or ayakaleaf-start (all).
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /var/lib/mongodb /var/log/mongodb' \
      'mongosh --quiet --eval "db.adminCommand({ping: 1})" >/dev/null 2>&1 \' \
      '  || mongod --replSet overleaf --bind_ip 127.0.0.1 --dbpath /var/lib/mongodb --logpath /var/log/mongodb/mongod.log --fork >/dev/null' \
      'until mongosh --quiet --eval "db.adminCommand({ping: 1})" >/dev/null 2>&1; do sleep 0.5; done' \
      'mongosh --quiet --eval "try { rs.status() } catch (e) { rs.initiate({_id: \"overleaf\", members: [{_id: 0, host: \"127.0.0.1:27017\"}]}) }" >/dev/null' \
      'until mongosh --quiet --eval "quit(db.hello().isWritablePrimary ? 0 : 1)" >/dev/null 2>&1; do sleep 0.5; done' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes --bind 127.0.0.1 --save "" --appendonly no --dir /tmp' \
      'until redis-cli ping >/dev/null 2>&1; do sleep 0.5; done' \
      'echo "MongoDB and Redis are ready"' \
      > /usr/local/bin/ayakaleaf-test-services \
&&  printf '%s\n' '#!/bin/sh' 'set -e' \
      'ayakaleaf-test-services' \
      'pgrep -f /sbin/my_init >/dev/null || (/sbin/my_init >/var/log/overleaf/my_init.log 2>&1 &)' \
      'i=0; until curl -fs http://127.0.0.1/status >/dev/null; do' \
      '  i=$((i+1)); [ $i -lt 300 ] || { echo "Overleaf did not start; see /var/log/overleaf/"; exit 1; }; sleep 1' \
      'done' \
      'echo "Ayakaleaf Pro is up on http://127.0.0.1/"' \
      > /usr/local/bin/ayakaleaf-start \
&&  chmod +x /usr/local/bin/ayakaleaf-test-services /usr/local/bin/ayakaleaf-start

# Start the whole stack once: the init scripts run the database migrations, and a working login page shows the image
# is usable offline. Then run the web unit tests (core and modules/*) against their own test database, leaving out the
# files that test Overleaf SaaS-only features (subscriptions, managed groups, SheerID) that CE builds do not ship.
# vitest's --exclude does not reach the projects in vitest.config.js, so the files to run are listed instead.
# Test failures are logged, not fatal.
RUN ayakaleaf-start \
&&  curl -fs -o /dev/null http://127.0.0.1/login \
&&  (cd services/web \
     && env -u OVERLEAF_CONFIG NODE_ENV=test MONGO_URL=mongodb://127.0.0.1/test-overleaf \
          yarn run test:unit $(find test/unit/src modules/*/test/unit -name '*.test.mjs' \
            | grep -vE 'Settings/Settings|Subscription/Subscription(Controller|Locator|Updater)|User/UserAuditLogHandler') \
     || echo "WARNING: web unit tests reported failures") \
&&  (mongosh --quiet --eval "db.adminCommand({shutdown: 1})" >/dev/null 2>&1 || true)
