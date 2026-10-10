# OSS Scanner build for laravolt/laravolt (https://github.com/laravolt/laravolt).
# Built with the laravolt/laravolt checkout as build context. Network is available only during this
# build; the audit runs offline.
#
# Mirrors .github/workflows/laravel.yml ("Laravolt Platform"): PHP 8.4 + Node 22, install the package
# into a fresh laravolt/laravel-starter-kit app through a Composer path repository, run
# `laravolt:install`, migrate SQLite, run the app's feature tests. Pint and the Playwright browser test
# from CI are skipped. In addition, the package's own Pest suite is installed in /src so the scanner
# can run and extend it.
FROM php:8.4-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_HOME=/opt/composer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Node 22, as in CI (actions/setup-node node-version 22).
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# CI extension list: bcmath, ctype, curl, dom, exif, fileinfo, gd, mbstring, pdo_sqlite, sockets,
# sqlite3, tokenizer, xml, zip. ctype/curl/dom/fileinfo/mbstring/pdo_sqlite/sqlite3/tokenizer/xml ship
# with the official php image; intl is added because Laravel's number/locale helpers use it.
COPY --from=mlocati/php-extension-installer:2 /usr/bin/install-php-extensions /usr/local/bin/
RUN install-php-extensions bcmath exif gd sockets zip intl \
    && php -r 'foreach (["bcmath","gd","pdo_sqlite","sockets","zip"] as $e) { if (!extension_loaded($e)) { fwrite(STDERR, "missing $e\n"); exit(1); } }'

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# scanner contract: the checkout lives inside the image, at /src
COPY . /src

# 1) The package's own dependencies and test suite (tests/, Pest). phpunit.xml.example targets
#    PostgreSQL; the environment variables below switch it to in-memory SQLite.
WORKDIR /src
RUN composer update --prefer-stable --prefer-dist --no-progress --no-scripts \
    && cp -n phpunit.xml.example phpunit.xml
ENV DB_CONNECTION=sqlite \
    DB_DATABASE=:memory:
RUN vendor/bin/pest --no-coverage || echo "WARNING: package test suite reported failures"

# 2) A host Laravel app, exactly like CI, at /app. vendor/laravolt/laravolt is a symlink to /src.
WORKDIR /
RUN composer create-project laravolt/laravel-starter-kit --no-install --no-ansi --no-scripts --prefer-dist /app
WORKDIR /app
RUN php -r "file_exists('.env') || copy('.env.example', '.env');" \
    && mkdir -p database && touch database/database.sqlite \
    && composer config repositories.laravolt '{"type":"path","url":"/src","options":{"symlink":true,"versions":{"laravolt/laravolt":"dev-master"}}}' \
    && composer update --no-ansi --no-scripts --no-progress --prefer-dist \
    && php artisan --version \
    && php artisan key:generate \
    && chmod -R 777 storage bootstrap/cache
RUN DB_DATABASE=/app/database/database.sqlite php artisan laravolt:install --no-interaction \
    && DB_DATABASE=/app/database/database.sqlite php artisan migrate --force
RUN php artisan test tests/Feature --no-coverage || echo "WARNING: starter-kit feature tests reported failures"
