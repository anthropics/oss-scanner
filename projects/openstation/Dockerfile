# OpenStation, for Anthropic's OSS Scanner (https://github.com/anthropics/oss-scanner). Kept beside project.yaml; the scanner
# copies it into the checkout as .oss-scanner/Dockerfile and builds it with the checkout as the context.
#
# /src              this repository: the OpenStation plugin, with its PHP dev dependencies installed (vendor/) and
#                   its JavaScript bundles built into assets/js/ by `npm run build`, as docs/DEVELOPMENT.md describes
# /var/www/html     a stock WordPress install (the latest release) that Apache serves; its plugin directory
#                   wp-content/plugins/desktop-mode is a symlink to /src, so a patch to /src takes effect on the
#                   next request. `desktop-mode` is the plugin's slug on WordPress.org; OpenStation is its name.
# /wordpress-phpunit  the WordPress PHPUnit test library of the same release, which tests/phpunit/bootstrap.php
#                   looks for there (it is what wp-env's cli container provides)
#
# The site is served by Apache with mod_rewrite and AllowOverride All. The database is MariaDB. Start both with
# `wp-start`; the site listens on http://127.0.0.1/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_TESTS_DIR=/wordpress-phpunit

# mysqli is the extension WordPress itself uses; the rest are the ones the WordPress hosting handbook recommends.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libavif-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp --with-avif \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node and npm for the Vite build. package.json asks for node ^24 || ^26.
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP: errors are logged, not shown; OPcache picks up edited files immediately so a patch can be
# checked straight away.
RUN { echo 'memory_limit=256M'; \
      echo 'upload_max_filesize=64M'; \
      echo 'post_max_size=64M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/dev/stderr'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

# Apache serves /var/www/html with .htaccess enabled and follows the plugin symlink into /src.
RUN a2enmod rewrite headers expires \
    && printf '<Directory /var/www/html>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\n<Directory /src>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
         > /etc/apache2/conf-available/wordpress.conf \
    && a2enconf wordpress

# wp-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop

# WordPress itself: the latest release, and the PHPUnit test library of that same release from wordpress-develop
# (tests/phpunit/includes and tests/phpunit/data), laid out the way wp-env lays it out for tests/phpunit/bootstrap.php.
RUN wp core download --path=/var/www/html --version=latest \
    && version="$(wp core version --path=/var/www/html)" \
    && echo "WordPress $version" \
    && git clone -q --depth 1 --branch "$version" https://github.com/WordPress/wordpress-develop.git /tmp/wordpress-develop \
    && mkdir -p /wordpress-phpunit \
    && cp -R /tmp/wordpress-develop/tests/phpunit/includes /tmp/wordpress-develop/tests/phpunit/data /wordpress-phpunit/ \
    && sed -e "s!dirname( __FILE__ ) . '/src/'!'/var/www/html/'!" \
           -e "s/youremptytestdbnamehere/wordpress_test/" \
           -e "s/yourusernamehere/wordpress/" \
           -e "s/yourpasswordhere/wordpress/" \
           -e "s/'localhost'/'127.0.0.1'/" \
           /tmp/wordpress-develop/wp-tests-config-sample.php > /wordpress-phpunit/wp-tests-config.php \
    && rm -rf /tmp/wordpress-develop \
    && mkdir -p /var/www/html/wp-content/uploads

# scanner contract: the OpenStation checkout lives inside the image, at /src. The install loads it from there.
COPY . /src
WORKDIR /src
RUN ln -s /src /var/www/html/wp-content/plugins/desktop-mode

# PHP dev dependencies (PHPUnit 9 via yoast/phpunit-polyfills, PHPCS with the WordPress standards), then the JavaScript
# build. assets/js/ is gitignored, so every bundle the site enqueues has to be produced here, while the network is up.
RUN composer install --no-progress
RUN npm ci --no-audit --no-fund && npm run build

# Install a working single-site WordPress on MariaDB, with one user per default role for access-control reproductions,
# the plugin activated, and OpenStation switched on for every one of those users (the per-user opt-in that the admin bar
# toggle sets, user meta `desktop_mode_mode`). WP_ENVIRONMENT_TYPE is `local`, as it is under wp-env, so that application
# passwords work over plain HTTP (core refuses them otherwise) and two installs can pair over HTTP:
#   admin / admin               administrator (has unfiltered_html)
#   editor / editor             editor        (has unfiltered_html)
#   author / author             author
#   contributor / contributor   contributor
#   subscriber / subscriber     subscriber
#   (anonymous)                 no login
# A second, empty database, wordpress_test, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE wordpress_test; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON wordpress_test.* TO 'wordpress'@'%';" \
    && wp config create --path=/var/www/html --dbname=wordpress --dbuser=wordpress --dbpass=wordpress --dbhost=127.0.0.1 \
         --skip-check \
    && wp config set --path=/var/www/html WP_ENVIRONMENT_TYPE local \
    && wp core install --path=/var/www/html --url=http://127.0.0.1 --title="OSS Scanner OpenStation" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for role in editor author contributor subscriber; do \
         wp user create --path=/var/www/html "$role" "$role@example.com" --role="$role" --user_pass="$role"; \
       done \
    && wp plugin activate --path=/var/www/html desktop-mode \
    && for user in admin editor author contributor subscriber; do \
         wp user meta update --path=/var/www/html "$user" desktop_mode_mode 1; \
       done \
    && wp rewrite structure --path=/var/www/html '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > /var/www/html/.htaccess \
    && chown -R www-data:www-data /var/www/html/wp-content/uploads \
    && wp plugin list --path=/var/www/html \
    && wp user list --path=/var/www/html --fields=user_login,roles \
    && curl -fsS -o /dev/null http://127.0.0.1/wp-login.php \
    && test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/wp-json/desktop-mode/v1/session)" = 401 \
    && wp-stop

# Run a small slice of the PHPUnit suite and the Vitest suite so you know the image works, but do not let a failing test
# abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --configuration tests/phpunit/phpunit.xml.dist --filter Tests_OpenStation_AdminBarDesktopToggle \
          || echo "WARNING: phpunit reported failures") \
    && (npm run test:js -- --reporter=dot tests/vitest/bundle-shared-state.test.ts || echo "WARNING: vitest reported failures") \
    && wp-stop
