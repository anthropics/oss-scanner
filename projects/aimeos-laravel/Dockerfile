FROM php:8.5-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl unzip python3 mariadb-server mariadb-client \
      libicu-dev libzip-dev libonig-dev libpng-dev libjpeg62-turbo-dev \
      libfreetype6-dev libwebp-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" bcmath gd intl mbstring pdo_mysql zip \
    && echo 'memory_limit=1G' > /usr/local/etc/php/conf.d/oss-scanner.ini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Scanner contract: the checkout lives at /src.
COPY . /src
WORKDIR /src

# Match the PHP 8.5 CI dependency selection, including the optional MCP bridge.
RUN composer require --no-interaction --no-update 'laravel/framework:~13.0' \
    && composer require --no-interaction --no-update --dev \
      'phpunit/phpunit:~12.0' 'laravel/mcp:^0.9' \
    && composer update --no-interaction --prefer-dist --no-progress

# Processes do not survive image creation. Provide explicit helpers that work
# in the scanner's offline shell without relying on an image entrypoint.
RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-start-db <<'SCRIPT'
#!/bin/sh
set -eu
if ! mariadb-admin ping --silent >/dev/null 2>&1; then
    service mariadb start
fi
mariadb <<'SQL'
CREATE DATABASE IF NOT EXISTS laravel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'aimeos'@'localhost' IDENTIFIED BY 'aimeos';
CREATE USER IF NOT EXISTS 'aimeos'@'127.0.0.1' IDENTIFIED BY 'aimeos';
GRANT ALL PRIVILEGES ON laravel.* TO 'aimeos'@'localhost';
GRANT ALL PRIVILEGES ON laravel.* TO 'aimeos'@'127.0.0.1';
SQL
SCRIPT
cat > /usr/local/bin/scanner-test <<'SCRIPT'
#!/bin/sh
set -eu
scanner-start-db
cd /src
exec vendor/bin/phpunit --no-coverage "$@"
SCRIPT
chmod +x /usr/local/bin/scanner-start-db /usr/local/bin/scanner-test
SH

# The suite's first setup test creates the schema and unittest fixtures.
# Preserve the environment for investigation if a project test fails.
RUN (scanner-test || echo 'WARNING: PHPUnit reported failures') \
    && mariadb -e 'DROP DATABASE IF EXISTS laravel' \
    && service mariadb stop
