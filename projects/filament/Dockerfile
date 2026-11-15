FROM node:22-bookworm-slim AS node
FROM composer:2 AS composer
FROM php:8.4-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git unzip libfreetype6-dev libicu-dev \
        libjpeg62-turbo-dev libonig-dev libpng-dev libsqlite3-dev libzip-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j2 bcmath exif gd intl mbstring pcntl pdo_sqlite sockets zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/ /usr/local/
COPY --from=composer /usr/bin/composer /usr/local/bin/composer

COPY . /src
WORKDIR /src

RUN composer install --prefer-dist --no-interaction --no-progress --no-scripts
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npm run build \
    && npx playwright install --with-deps chromium
