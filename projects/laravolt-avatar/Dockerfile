# OSS Scanner build for laravolt/avatar (https://github.com/laravolt/avatar).
# Built with the laravolt/avatar checkout as build context. Network is available only during this build;
# the audit runs offline, so everything the package and its tests need is installed here.
# Mirrors .github/workflows/run-tests.yml (PHP 8.3 job, prefer-stable, same extension set).
FROM php:8.3-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_HOME=/opt/composer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip \
    && rm -rf /var/lib/apt/lists/*

# gd (with freetype/jpeg/webp) and imagick are the two Intervention Image v4 drivers used by
# src/Avatar.php::buildAvatar (HDAvatarResponse defaults to imagick). intl, zip, exif, bcmath, pcntl
# match run-tests.yml; dom, xml, mbstring, iconv, curl already ship with the official php image.
COPY --from=mlocati/php-extension-installer:2 /usr/bin/install-php-extensions /usr/local/bin/
RUN install-php-extensions gd imagick intl zip exif bcmath pcntl \
    && php -r 'exit(extension_loaded("gd") && extension_loaded("imagick") && function_exists("imagettftext") ? 0 : 1);'

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# composer.lock is not committed (.gitignore), so resolve like the CI "prefer-stable" job.
RUN composer update --prefer-stable --prefer-dist --no-progress \
    && composer show --direct

# The suite needs no network (cache and Laravel facades are mocked). Do not fail the build on a red test.
RUN vendor/bin/phpunit -c phpunit.xml || echo "WARNING: phpunit reported failures"
