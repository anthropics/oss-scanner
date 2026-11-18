# HumHub core.
#
# /src    the HumHub git checkout (the repository named in project.yaml), installed in place and served by Apache
#         with .htaccess enabled and pretty URLs, on MariaDB, the way https://docs.humhub.org/docs/admin/installation
#         describes a production install.
#
# Start MariaDB and Apache with `humhub-start`; the site listens on http://127.0.0.1/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client nodejs npm \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev libldap2-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-configure ldap --with-libdir="lib/$(dpkg-architecture --query DEB_BUILD_MULTIARCH)" \
    && docker-php-ext-install -j"$(nproc)" gd zip intl exif ldap pdo_mysql \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g grunt-cli
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Production-like PHP: errors are logged, not shown.
RUN cp "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini" \
    && { echo 'memory_limit=512M'; \
         echo 'upload_max_filesize=32M'; \
         echo 'post_max_size=32M'; \
         echo 'date.timezone=UTC'; \
         echo 'error_log=/dev/stderr'; \
         echo 'opcache.validate_timestamps=1'; \
         echo 'opcache.revalidate_freq=0'; \
       } > "$PHP_INI_DIR/conf.d/oss-scanner.ini"

# Apache serves /src with .htaccess enabled.
RUN a2enmod rewrite headers expires \
    && sed -ri 's!/var/www/html!/src!g' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /src>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
         > /etc/apache2/conf-available/humhub.conf \
    && a2enconf humhub \
    && git config --system --add safe.directory '*'

# humhub-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
# as-www-data runs a command as the user Apache runs as; `yii` runs HumHub's console as that user.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/humhub-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin -uroot -proot shutdown 2>/dev/null; true' \
      > /usr/local/bin/humhub-stop \
    && printf '%s\n' '#!/bin/sh' 'exec setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp "$@"' \
      > /usr/local/bin/as-www-data \
    && printf '%s\n' '#!/bin/sh' 'cd /src/protected && exec as-www-data php yii "$@"' > /usr/local/bin/yii \
    && chmod +x /usr/local/bin/humhub-start /usr/local/bin/humhub-stop /usr/local/bin/as-www-data /usr/local/bin/yii

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Dependencies, including the dev dependencies (Codeception) so the test suite runs offline, and the npm tooling
# (Grunt) that the production asset build uses.
RUN composer install --no-progress --optimize-autoloader \
    && npm ci --no-audit --no-fund \
    && cp .htaccess.dist .htaccess \
    && printf '%s\n' \
         'HUMHUB_CONFIG__COMPONENTS__URL_MANAGER__SHOW_SCRIPT_NAME=false' \
         'HUMHUB_CONFIG__COMPONENTS__URL_MANAGER__ENABLE_PRETTY_URL=true' \
         > .env \
    && chown -R www-data:www-data /src

# Install a working site on MariaDB, with production assets, and these accounts:
#   admin / admin       system administrator (member of the Administrator group)
#   alice / alice       plain user
#   bobby / bobby       plain user
#   (anonymous)         no login
# A second database, humhub_test, is prepared for the Codeception suite (root/root on 127.0.0.1, as in CI).
RUN humhub-start \
    && mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA unix_socket OR mysql_native_password USING PASSWORD('root'); \
         CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY 'root'; GRANT ALL ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; \
         CREATE DATABASE humhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; \
         CREATE DATABASE humhub_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; \
         CREATE USER 'humhub'@'127.0.0.1' IDENTIFIED BY 'humhub'; GRANT ALL ON humhub.* TO 'humhub'@'127.0.0.1'; \
         FLUSH PRIVILEGES;" \
    && yii installer/write-db-config 127.0.0.1 humhub humhub humhub \
    && yii installer/install-db \
    && yii installer/write-site-config "OSS Scanner HumHub" humhub@example.com \
    && yii installer/set-base-url http://127.0.0.1 \
    && yii installer/create-admin-account admin admin@example.com admin \
    && yii user/create alice alice@example.com Alice Example && yii user/set-password alice alice \
    && yii user/create bobby bobby@example.com Bobby Example && yii user/set-password bobby bobby \
    && as-www-data mkdir -p protected/humhub/resources/build && rm -rf protected/humhub/resources/build/*/ \
    && yii asset humhub/config/assets.php humhub/config/assets-prod.php \
    && yii cache/flush-all \
    && yii content-search/rebuild \
    && cd /src && as-www-data php protected/humhub/tests/codeception/bin/yii migrate/up --includeModuleMigrations=1 --interactive=0 \
    && as-www-data php protected/humhub/tests/codeception/bin/yii installer/auto \
    && as-www-data php protected/humhub/tests/codeception/bin/yii content-search/rebuild \
    && humhub-stop

# humhub-test runs Codeception as www-data, e.g. `humhub-test unit` or `humhub-test -m user functional`.
# Acceptance tests need Selenium and are not available here.
RUN printf '%s\n' '#!/bin/sh' \
      'module=""; if [ "$1" = "-m" ]; then module="$2"; shift 2; fi' \
      'dir=/src/protected/humhub/tests; [ -n "$module" ] && dir=/src/protected/humhub/modules/$module/tests' \
      'cd "$dir" && exec as-www-data php /src/protected/vendor/codeception/codeception/codecept run "$@"' \
      > /usr/local/bin/humhub-test \
    && chmod +x /usr/local/bin/humhub-test

# Smoke-test the site and the test setup, without letting a failing test abort the build.
RUN humhub-start \
    && curl -fsS -o /dev/null http://127.0.0.1/user/auth/login \
    && (test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/protected/config/dynamic.php)" != 200 \
          || echo "WARNING: protected/config/dynamic.php is served") \
    && (humhub-test -m user unit || echo "WARNING: user module unit tests reported failures") \
    && humhub-stop

# Keep build products out of the checkout's `git status`.
RUN printf '.oss-scanner/\n.env\n.htaccess\n' >> /src/.git/info/exclude || true

WORKDIR /src
