# Sulu CMS (PHP/Symfony monorepo). Builds the checkout at /src with its dev dependencies.
FROM php:8.4-cli-bookworm
ENV DEBIAN_FRONTEND=noninteractive COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_NO_INTERACTION=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip mariadb-server libicu-dev libzip-dev libpng-dev libjpeg-dev libfreetype6-dev libxml2-dev libonig-dev libffi-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" intl zip gd exif ffi pdo_mysql opcache \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# The functional tests exhaust PHP's default 128M.
RUN echo 'memory_limit=1G' > /usr/local/etc/php/conf.d/oss-scanner.ini

# The functional tests need a database. MariaDB has no init system here: `sulu-db-start` starts it and is safe to run
# again. Doctrine appends _test to the database name in the test env, so the URL names `sulu` and tests use `sulu_test`.
ENV DATABASE_URL="mysql://sulu:sulu@127.0.0.1:3306/sulu?serverVersion=10.11.0-MariaDB&charset=utf8mb4"
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      > /usr/local/bin/sulu-db-start \
    && chmod +x /usr/local/bin/sulu-db-start \
    && sulu-db-start \
    && mariadb -e "CREATE DATABASE sulu; CREATE DATABASE sulu_test; \
         CREATE USER 'sulu'@'%' IDENTIFIED BY 'sulu'; \
         GRANT ALL ON sulu.* TO 'sulu'@'%'; GRANT ALL ON sulu_test.* TO 'sulu'@'%';" \
    && mariadb-admin shutdown

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Dependencies are fetched here because the audit runs without network access.
RUN composer install --prefer-dist --no-progress

# Run the cheap static checks so the image is known to work; a failure must not abort the build.
RUN (composer lint-container || composer lint-yaml || echo "WARNING: lint reported problems")
