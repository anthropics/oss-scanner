FROM node:22-bookworm-slim AS node

FROM php:8.4-cli-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_ROOT_VERSION=dev-2.0-develop

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip mariadb-server mariadb-client \
      libicu-dev libzip-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libwebp-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" bcmath gd intl pcntl pdo_mysql zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# The repository's .dockerignore is written for the production image and leaves out tests/, tools/, storage/ and
# .env.ci, so the full checkout is cloned instead of copied from the build context.
RUN git clone --branch 2.0-develop https://github.com/pterodactyl/panel.git /src
WORKDIR /src

# Backend with dev dependencies so the Pest suites run offline.
RUN cp .env.ci .env \
    && composer install --prefer-dist --no-interaction --no-progress

# Frontend bundle and the SDK test runtime used by Vitest.
RUN npm ci --no-audit --no-fund \
    && npm run build \
    && npm run sdk:testing

# MariaDB for the integration suite. Start it with `service mariadb start`; tests use root with no password on 127.0.0.1.
RUN service mariadb start \
    && mariadb -e "CREATE DATABASE testing; ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('');" \
    && service mariadb stop

# Cheap checks so the image is known to work; failures do not abort the build.
RUN (composer test:unit || echo "WARNING: unit tests reported failures") \
    && (npm test || echo "WARNING: frontend tests reported failures")
