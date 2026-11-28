# Coolify (coollabsio/coolify) for Anthropic OSS Scanner.
#
# Build context is the Coolify git checkout. Network is available only during
# this Dockerfile; the scan that follows runs offline, so every Composer and
# npm dependency must be fetched here.
#
# /src  Laravel 12 + Livewire + Vite app, with require-dev, built assets,
#       and a testing .env (sqlite :memory:, no real secrets).

FROM php:8.4-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    NODE_ENV=production

# System libs + PHP extensions Coolify / Laravel need at install and runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip procps \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev \
      libzip-dev libicu-dev libpq-dev libsqlite3-dev libxml2-dev \
      libonig-dev libcurl4-openssl-dev libssl-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" \
      bcmath curl gd intl mbstring pcntl pdo_mysql pdo_pgsql pdo_sqlite \
      sockets xml zip \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && rm -rf /var/lib/apt/lists/* /tmp/pear

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node.js 22 LTS (Vite / frontend build). npm comes with the official image.
COPY --from=node:22-bookworm /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node -v && npm -v

# Production-like PHP: errors logged, not displayed; enough memory for artisan.
RUN { echo 'memory_limit=512M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/dev/stderr'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

# scanner contract: the Coolify checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# PHP dependencies (include require-dev so Pest / PHPStan are available offline).
RUN composer install --no-interaction --prefer-dist --no-progress

# Frontend assets (package-lock.json is present; prefer npm over bun).
RUN npm ci && npm run build

# Testing env only — copy committed .env.testing (APP_KEY is a dummy, DB is
# sqlite :memory:). Never bake production secrets into this image.
RUN if [ -f .env.testing ]; then \
      cp .env.testing .env; \
    else \
      printf '%s\n' \
        'APP_ENV=testing' \
        'APP_KEY=base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' \
        'APP_DEBUG=true' \
        'DB_CONNECTION=testing' \
        'CACHE_DRIVER=array' \
        'SESSION_DRIVER=array' \
        'QUEUE_CONNECTION=sync' \
        'MAIL_MAILER=array' \
        'SELF_HOSTED=true' \
        > .env; \
    fi \
    && php artisan package:discover --ansi || true \
    && php artisan --version

# Cheap smoke checks. A failing test must not abort the build.
RUN php artisan about || echo "WARNING: artisan about failed" \
    && (./vendor/bin/pest --version || echo "WARNING: pest not available") \
    && (./vendor/bin/pest tests/Unit --bail 2>/dev/null \
        || echo "WARNING: unit smoke reported failures")

WORKDIR /src
