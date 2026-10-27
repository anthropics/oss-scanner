# Ruby on Rails.
#
# /src    the rails/rails checkout, bundled with every Gemfile group so the framework test suites run offline.
#
# The services the suites talk to (PostgreSQL, MariaDB, Redis, Memcached) are installed in the image, and the Active
# Record test databases are created at build time. There is no init system in the container: run `rails-services-start`
# before the test suites that need them. It is safe to run again.
#
# Run a framework's tests from its directory, as maintainers do:
#   cd /src/actionpack && bin/test test/dispatch/request_test.rb
#   cd /src/activerecord && bundle exec rake test:sqlite3      # or test:postgresql, test:mysql2, test:trilogy
#   cd /src/actiontext && bin/test test/system                 # system tests run headless Chromium or Firefox
#   cd /src/railties && bundle exec rake test                  # one process per file; railties needs that
FROM ruby:4.0-trixie

# MYSQL_SOCK points both MySQL adapters' tests at MariaDB's socket. SE_OFFLINE keeps Selenium Manager to the browsers
# and drivers installed here when system tests load.
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    BUNDLE_JOBS=8 \
    BUNDLE_RETRY=3 \
    MYSQL_SOCK=/run/mysqld/mysqld.sock \
    SE_OFFLINE=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config procps locales \
      sqlite3 libsqlite3-dev \
      postgresql postgresql-contrib libpq-dev \
      mariadb-server mariadb-client libmariadb-dev \
      redis-server memcached \
      libyaml-dev libxml2-dev libxslt1-dev libffi-dev \
      libvips-dev imagemagick ffmpeg mupdf mupdf-tools poppler-utils \
      tzdata tzdata-legacy \
      chromium chromium-driver firefox-esr \
    && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# Chromium won't start as root without --no-sandbox; Debian's launcher reads extra flags from /etc/chromium.d.
RUN echo 'export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --no-sandbox"' > /etc/chromium.d/no-sandbox

# Action Pack's system tests are driven by headless Firefox. Debian doesn't package geckodriver.
RUN ln -sf firefox-esr /usr/bin/firefox \
    && case "$(dpkg --print-architecture)" in arm64) arch=linux-aarch64 ;; *) arch=linux64 ;; esac \
    && curl -fsSL "https://github.com/mozilla/geckodriver/releases/download/v0.37.1/geckodriver-v0.37.1-$arch.tar.gz" \
       | tar -xz -C /usr/local/bin geckodriver

# The JavaScript packages need Node 24; Debian ships 20. Take only Node itself from the official image, so Ruby's
# /usr/local stays as it is.
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g yarn@1

# MariaDB 11.8 turns on snapshot isolation by default; the MySQL adapters' tests expect MySQL's behavior.
RUN printf '[mysqld]\ninnodb_snapshot_isolation = OFF\n' > /etc/mysql/mariadb.conf.d/99-rails.cnf

# rails-services-start starts PostgreSQL, MariaDB, Redis and Memcached on their default local ports and sockets.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'pg_ctlcluster "$(ls /etc/postgresql)" main start 2>/dev/null || true' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes >/dev/null' \
      'pgrep -x memcached >/dev/null || memcached -d -u nobody -m 1024' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'until pg_isready -q; do sleep 0.5; done' \
      > /usr/local/bin/rails-services-start \
    && chmod +x /usr/local/bin/rails-services-start

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN bundle install && yarn install --frozen-lockfile

# Railties' tests generate apps and plugins and bundle them, and those need gems the checkout's lockfile doesn't (a newer
# puma, say). Bundle a fresh app and plugin now, so the gems are installed and Bundler's cached index resolves to them.
RUN bundle exec ruby railties/exe/rails new /tmp/app_deps --skip-bundle --skip-git --quiet \
    && bundle exec ruby railties/exe/rails plugin new /tmp/plugin_deps --skip-bundle --skip-git --quiet \
    && sed -i 's|^gem "rails".*|gem "rails", path: "/src"|' /tmp/app_deps/Gemfile \
    && sed -i 's|"TODO[^"]*"|"https://example.com"|g' /tmp/plugin_deps/plugin_deps.gemspec \
    && sed -i '/^gem "rails"/d' /tmp/plugin_deps/Gemfile \
    && echo 'gem "rails", path: "/src"' >> /tmp/plugin_deps/Gemfile \
    && (cd /tmp/app_deps && bundle install) \
    && (cd /tmp/plugin_deps && bundle install) \
    && rm -rf /tmp/app_deps /tmp/plugin_deps

# Active Record's database tests connect over local sockets as the current user: root in this image.
RUN rails-services-start \
    && su postgres -c "createuser --superuser root" \
    && cd activerecord \
    && bundle exec rake db:postgresql:rebuild db:mysql:rebuild

# Smoke-test the image without letting a failing test abort the build.
RUN rails-services-start \
    && (cd activesupport && bin/test test/message_verifier_test.rb) \
    && (cd activerecord && bundle exec rake test:sqlite3 TEST=test/cases/base_test.rb) \
    && (cd activerecord && bundle exec rake test:postgresql TEST=test/cases/base_test.rb) \
    && (cd activerecord && bundle exec rake test:mysql2 TEST=test/cases/base_test.rb) \
    || echo "WARNING: smoke tests reported failures"
