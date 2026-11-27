# Builds Pelican Panel (Laravel 12, PHP 8.4) from the checkout at /src, with Composer and Node
# dependencies installed and a migrated SQLite test database, so the test suite runs offline.
FROM node:22-bookworm-slim AS node
FROM composer:2 AS composer
FROM php:8.4-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    APP_ENV=testing \
    APP_KEY=base64:dGhpc2lzYXRlc3RrZXlmb3JzY2FubmVyb25seTEyMzQ= \
    APP_URL=http://localhost/ \
    DB_CONNECTION=sqlite \
    DB_DATABASE=testing.sqlite \
    CACHE_STORE=array \
    SESSION_DRIVER=array \
    QUEUE_CONNECTION=sync \
    MAIL_MAILER=array

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git unzip libfreetype6-dev libicu-dev libjpeg62-turbo-dev \
        libonig-dev libpng-dev libsqlite3-dev libzip-dev libxml2-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" bcmath exif gd intl mbstring pcntl pdo_mysql pdo_sqlite sockets zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/ /usr/local/
COPY --from=node /opt/ /opt/
COPY --from=composer /usr/bin/composer /usr/local/bin/composer

COPY . /src
WORKDIR /src

RUN composer install --prefer-dist --no-interaction --no-progress --no-scripts \
    && composer dump-autoload
RUN yarn --version && yarn install --frozen-lockfile --ignore-scripts && yarn build

# A migrated, seeded SQLite database, as in the project's CI.
RUN touch database/testing.sqlite && php artisan migrate --force --seed

# No PHP memory limit, as in the project's CI (setup-php).
RUN echo 'memory_limit=-1' > /usr/local/etc/php/conf.d/zz-memory.ini

# Baseline tests (unit and integration, as in CI). A failing test must not abort the build.
RUN (SKIP_MIGRATIONS=true DB_HOST=UNIT_NO_DB vendor/bin/pest tests/Unit --do-not-fail-on-phpunit-warning \
     && CREATE_SNAPSHOTS=false vendor/bin/pest tests/Integration --do-not-fail-on-phpunit-warning) \
    || echo "WARNING: baseline tests reported failures"

CMD ["bash"]
