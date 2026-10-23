# syntax=docker/dockerfile:1
# Public source at /src; WordPress/WooCommerce at /var/www/html; test WordPress under /tmp.
FROM php:8.3-apache-bookworm

# WP_TESTS_DIR and WP_CORE_DIR pin the PHPUnit layout above for bin/install-wp-tests.sh and tests/bootstrap.php,
# whatever TMPDIR is at run time.
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html \
    WP_TESTS_DIR=/tmp/wordpress-tests-lib \
    WP_CORE_DIR=/tmp/wordpress

# mysqli is what WordPress uses; the rest are the extensions the WordPress hosting handbook recommends.
# subversion: install-wp-tests.sh checks the test library out of develop.svn.wordpress.org.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev libonig-dev zip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath mbstring \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node and npm match the plugin asset-build toolchain.
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP (php.ini-production values): errors are logged to /var/log/php-error.log, not shown, and not
# sent to stderr (PHPUnit turns stderr output of process-isolated tests into errors); output_buffering=4096 as in
# php.ini-production for Apache (the CLI SAPI always forces it to 0); OPcache picks up edited files immediately.
RUN { echo 'memory_limit=512M'; \
      echo 'upload_max_filesize=64M'; \
      echo 'post_max_size=64M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/var/log/php-error.log'; \
      echo 'output_buffering=4096'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini \
    && touch /var/log/php-error.log && chmod 666 /var/log/php-error.log

# Apache serves /var/www/html with .htaccess enabled.
RUN a2enmod rewrite headers expires \
    && printf '<Directory /var/www/html>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
         > /etc/apache2/conf-available/wordpress.conf \
    && a2enconf wordpress

# wp-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'for attempt in $(seq 1 120); do mariadb-admin ping --silent 2>/dev/null && break; sleep 0.5; done' \
      'mariadb-admin ping --silent' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop


COPY . /src
WORKDIR /src
# Public-source build only. Full integration requires private Bookings and Product Add-Ons.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && composer install --no-progress --optimize-autoloader \
    && npm run build:webpack && npm run makepot
RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-test <<'TEST'
#!/bin/bash
set -euo pipefail
cd /src
vendor/bin/phpunit --fail-on-empty-test-suite
vendor/bin/phpunit -c tests/isolated/phpunit.xml.dist --fail-on-empty-test-suite
printf '%s\n' 'Public unit suites only; Bookings/Product Add-Ons integration remains blocked.'
TEST
chmod +x /usr/local/bin/scanner-test
SH
