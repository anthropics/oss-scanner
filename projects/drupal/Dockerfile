# Drupal core.
#
# /src           the Drupal core git checkout (the repository named in project.yaml)
# /opt/drupal    a Drupal site built the way drupal.org documents it
#                (https://www.drupal.org/docs/develop/using-composer/starting-a-site-using-drupal-composer-project-templates):
#                `composer create-project drupal/recommended-project`, `composer require drush/drush`, then
#                `drush site:install`.
#
# The site is served by Apache with mod_rewrite and AllowOverride All, so Drupal's .htaccess protections apply as they
# do in production. The database is MariaDB, as on most production Drupal sites. Start both with `drupal-start`; the
# site listens on http://127.0.0.1/.
FROM php:8.5-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1

# The base image already provides OPcache.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" gd zip intl bcmath pdo_mysql \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Production-like PHP: errors are logged, not shown; a normal per-request memory limit; OPcache picks up edited files
# immediately so a patch can be checked straight away.
RUN { echo 'memory_limit=256M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/dev/stderr'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

# Apache serves /opt/drupal/web with .htaccess enabled.
RUN a2enmod rewrite headers expires \
    && sed -ri 's!/var/www/html!/opt/drupal/web!g' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /opt/drupal/web>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
         > /etc/apache2/conf-available/drupal.conf \
    && a2enconf drupal

# drupal-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/drupal-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/drupal-stop \
    && chmod +x /usr/local/bin/drupal-start /usr/local/bin/drupal-stop

# scanner contract: the Drupal core checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the site per drupal.org's Composer instructions, tracking Drupal core's main branch.
#
# Drupal 12 marks `tests` as `export-ignore` in core/.gitattributes, so the composer dist archive omits
# core/tests (including tests/bootstrap.php) and every module's tests. Install drupal/core from source
# (`preferred-install`) so PHPUnit can bootstrap and core's tests are present; everything else stays dist.
RUN composer create-project --no-install --no-progress --stability=dev drupal/recommended-project:dev-main /opt/drupal
WORKDIR /opt/drupal
RUN composer config preferred-install.drupal/core source \
    && composer install --no-progress
RUN composer require --no-progress drush/drush

# Test tooling (PHPUnit and friends), so core's unit, kernel and functional tests run offline.
RUN composer require --dev --no-progress -W drupal/core-dev:dev-main

# Install a working site on MariaDB with the standard profile, a private file system, and a non-admin user for
# access-control reproductions:
#   admin / admin       uid 1
#   editor / editor     role content_editor
#   (anonymous)         no login
ENV DRUSH_OPTIONS_URI=http://127.0.0.1 \
    SIMPLETEST_DB=mysql://drupal:drupal@127.0.0.1/drupal_test \
    SIMPLETEST_BASE_URL=http://127.0.0.1 \
    BROWSERTEST_OUTPUT_DIRECTORY=/tmp
RUN drupal-start \
    && mariadb -e "CREATE DATABASE drupal; CREATE DATABASE drupal_test; \
         CREATE USER 'drupal'@'%' IDENTIFIED BY 'drupal'; \
         GRANT ALL ON drupal.* TO 'drupal'@'%'; GRANT ALL ON drupal_test.* TO 'drupal'@'%';" \
    && mkdir -p /opt/drupal/private \
    && vendor/bin/drush site:install standard -y \
      --db-url=mysql://drupal:drupal@127.0.0.1/drupal \
      --site-name="OSS Scanner Drupal" --account-name=admin --account-pass=admin \
    && chmod u+w web/sites/default web/sites/default/settings.php \
    && echo "\$settings['file_private_path'] = '/opt/drupal/private';" >> web/sites/default/settings.php \
    && vendor/bin/drush user:create editor --password=editor --mail=editor@example.com \
    && vendor/bin/drush user:role:add content_editor editor \
    && vendor/bin/drush cache:rebuild \
    && vendor/bin/drush status \
    && chown -R www-data:www-data /opt/drupal \
    && drupal-stop

# drush and phpunit run as www-data, the user Apache runs as, so the site's files and database stay writable by both.
RUN printf '#!/bin/sh\nexec setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp /opt/drupal/vendor/bin/drush "$@"\n' \
      > /usr/local/bin/drush \
    && printf '#!/bin/sh\ncd /opt/drupal/web && exec setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp /opt/drupal/vendor/bin/phpunit -c core "$@"\n' \
      > /usr/local/bin/drupal-phpunit \
    && chmod +x /usr/local/bin/drush /usr/local/bin/drupal-phpunit

# Smoke-test the site and the test setup, without letting a failing test abort the build.
RUN drupal-start \
    && curl -fsS -o /dev/null http://127.0.0.1/user/login \
    && test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/core/modules/system/system.module)" = 403 \
    && (drupal-phpunit core/modules/user/tests/src/Functional/UserLoginTest.php --filter testLoginCacheTagsAndDestination \
          || echo "WARNING: core functional test reported failures") \
    && (drupal-phpunit core/modules/user/tests/src/Kernel --no-progress \
          || echo "WARNING: core user kernel tests reported failures") \
    && drupal-stop

# Keep build products out of the core checkout's `git status`.
RUN printf '.oss-scanner/\n' >> /src/.git/info/exclude || true

WORKDIR /src
