FROM node:22-bookworm AS node
FROM php:8.5-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    DB_DRIVER=sqlite \
    CI=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl unzip python3 build-essential sqlite3 \
      libcurl4-openssl-dev libonig-dev libxml2-dev libicu-dev libzip-dev \
      libsqlite3-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libwebp-dev \
      libgtk-3-0 libgbm1 libnotify4 libnss3 libxss1 libasound2 \
      libxtst6 xauth xvfb fonts-liberation \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" \
      bcmath curl exif gd intl mbstring pcntl pdo_sqlite zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Scanner contract: build with the Pagible checkout as context, at /src.
COPY . /src
WORKDIR /src

# Match PHP CI: resolve the monorepo's local Composer path repositories.
RUN composer update --no-interaction --prefer-dist --no-progress

# Fetch Cypress during the online build so component tests work offline.
ENV CYPRESS_VERIFY_TIMEOUT=120000
RUN npm ci --prefix admin \
    && npm ci --prefix webhooks/admin \
    && composer build \
    && cd admin && npx --no-install cypress verify

# Keep the environment available for investigation if a project test fails.
RUN echo 'memory_limit=1G' > /usr/local/etc/php/conf.d/oss-scanner.ini
RUN vendor/bin/phpunit || echo "WARNING: PHPUnit reported failures"
