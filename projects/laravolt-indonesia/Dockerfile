# OSS Scanner build for laravolt/indonesia (https://github.com/laravolt/indonesia).
# Built with the laravolt/indonesia checkout as build context. Network is available only during this
# build; the audit runs offline. The repo has no GitHub Actions workflow; .travis.yml (legacy) runs
# `composer update` + `vendor/bin/phpunit -c phpunit.xml`, which is what this file does on PHP 8.3.
FROM php:8.3-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_HOME=/opt/composer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip \
    && rm -rf /var/lib/apt/lists/*

# Tests run on orchestra/testbench with an in-memory SQLite database (tests/TestCase.php).
# pdo_sqlite ships with the official php image; intl/zip/bcmath are common Laravel needs.
COPY --from=mlocati/php-extension-installer:2 /usr/bin/install-php-extensions /usr/local/bin/
RUN install-php-extensions intl zip bcmath \
    && php -r 'exit(extension_loaded("pdo_sqlite") ? 0 : 1);'

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# No composer.lock is committed; resolve the newest stable set for PHP 8.3.
RUN composer update --prefer-stable --prefer-dist --no-progress \
    && composer show --direct

# phpunit.xml uses the 9.3 schema; newer PHPUnit warns but still runs. Do not fail the build on red tests.
RUN vendor/bin/phpunit -c phpunit.xml || echo "WARNING: phpunit reported failures"
