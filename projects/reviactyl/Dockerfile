FROM node:24-trixie-slim AS node
FROM php:8.5-cli-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    CI=true \
    APP_ENV=testing \
    APP_DEBUG=false \
    APP_URL=http://127.0.0.1:8000 \
    APP_TIMEZONE=UTC \
    APP_MAINTENANCE_DRIVER=file \
    DB_CONNECTION=sqlite \
    DB_DATABASE=/src/database/testing.sqlite \
    CACHE_STORE=array \
    CACHE_DRIVER=array \
    SESSION_DRIVER=array \
    QUEUE_CONNECTION=sync \
    MAIL_MAILER=array \
    BCRYPT_ROUNDS=4

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git unzip zip sqlite3 python3 \
        build-essential pkg-config \
        libfreetype6-dev libicu-dev libjpeg62-turbo-dev \
        libpng-dev libpq-dev libzip-dev \
        mariadb-server mariadb-client redis-server \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j"$(nproc)" \
        bcmath gd intl pcntl pdo_mysql pdo_pgsql zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

COPY . /src
WORKDIR /src

RUN composer install --no-interaction --no-progress --prefer-dist --no-scripts \
    && composer check-platform-reqs \
    && npm install --global "$(node -p "require('./package.json').packageManager.split('+')[0]")" \
    && pnpm install --frozen-lockfile

RUN cp .env.example .env \
    && mkdir -p bootstrap/cache storage/app/private storage/app/public \
        storage/framework/cache/data storage/framework/sessions \
        storage/framework/views storage/logs \
    && touch database/testing.sqlite \
    && php artisan key:generate --force --no-interaction \
    && php artisan package:discover --ansi \
    && php artisan filament:upgrade \
    && pnpm run build \
    && php artisan migrate --force --seed --no-interaction

RUN printf 'memory_limit=1G\n' > "$PHP_INI_DIR/conf.d/oss-scanner.ini" \
    && (vendor/bin/pest tests/Unit || echo 'WARNING: Panel unit tests reported failures') \
    && (vendor/bin/pest tests/Integration || echo 'WARNING: Panel integration tests reported failures') \
    && (pnpm test || echo 'WARNING: Panel frontend tests reported failures')

RUN php artisan migrate:fresh --force --seed --no-interaction

CMD ["bash"]
