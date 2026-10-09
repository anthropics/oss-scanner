# Pure-PHP composer library. CI tests PHP 8.3, 8.4 and 8.5 with ext-mbstring, and composer.json pins the
# platform to PHP 8.3.0, so the image uses the official PHP 8.3 CLI build (mbstring is compiled in).
# Dev dependencies (PHPUnit, PHPStan, php-cs-fixer) are installed here because the scan runs offline.
FROM php:8.3-cli-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# CI runs PHPUnit with memory_limit=256M (composer.json "test" script and .github/workflows/ci.yml).
RUN printf 'memory_limit=256M\n' > /usr/local/etc/php/conf.d/zz-oss-scanner.ini \
    && php -m | grep -qx mbstring

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN composer install --no-interaction --no-progress --prefer-dist \
    && composer dump-autoload --optimize

# Non-fatal smoke run of the suite; it needs no network.
RUN vendor/bin/phpunit || echo "WARNING: phpunit reported failures"
