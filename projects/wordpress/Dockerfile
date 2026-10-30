# WordPress core.
#
# /src           the wordpress-develop git checkout (the repository named in project.yaml), with its PHP and JavaScript
#                dependencies installed and its assets built into /src/src by `npm run build:dev`, as the project's
#                README describes for local development
# /src/src       the WordPress install that Apache serves; /src/wp-config.php configures it (WordPress looks one
#                directory above ABSPATH for wp-config.php)
#
# The site is served by Apache with mod_rewrite and AllowOverride All, so WordPress's .htaccess rules apply as they do
# in production. The database is MariaDB. Start both with `wp-start`; the site listens on http://127.0.0.1/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1

# The base image already provides OPcache. mysqli is the extension WordPress itself uses; the rest are the ones the
# WordPress hosting handbook recommends.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libavif-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp --with-avif \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node and npm for the asset build. wordpress-develop's .npmrc sets engine-strict, and package.json asks for
# node >= 24.18 and npm >= 11.16.
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g npm@11 \
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

# Apache serves /src/src with .htaccess enabled.
RUN a2enmod rewrite headers expires \
    && sed -ri 's!/var/www/html!/src/src!g' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /src/src>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
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

# scanner contract: the wordpress-develop checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# PHP dev dependencies (PHPUnit via yoast/phpunit-polyfills, PHPCS, PHPStan), then the JavaScript and CSS build. The
# build downloads the pinned Gutenberg release, so it has to happen here, while the network is up.
RUN composer install --no-progress
RUN npm ci --no-audit --no-fund && npm run build:dev

# Core does not vendor Gutenberg's source: package.json pins a Gutenberg commit (`gutenberg.sha`), and the build above
# downloads a prebuilt artifact of that commit into /src/gutenberg and copies it into src/wp-includes. Fetch the source
# of the same commit to /opt/gutenberg, so the shipped block editor code can be traced back to it offline.
RUN sha="$(node -p 'require("./package.json").gutenberg.sha')" \
    && git init -q /opt/gutenberg \
    && git -C /opt/gutenberg fetch -q --depth 1 https://github.com/WordPress/gutenberg.git "$sha" \
    && git -C /opt/gutenberg checkout -q FETCH_HEAD \
    && git -C /opt/gutenberg log -1 --format='Gutenberg source at %H'

# Install a working single-site WordPress on MariaDB, with one user per default role for access-control reproductions:
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
    && wp config create --path=/src/src --dbname=wordpress --dbuser=wordpress --dbpass=wordpress --dbhost=127.0.0.1 \
         --skip-check \
    && mv /src/src/wp-config.php /src/wp-config.php \
    && wp core install --path=/src/src --url=http://127.0.0.1 --title="OSS Scanner WordPress" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for role in editor author contributor subscriber; do \
         wp user create --path=/src/src "$role" "$role@example.com" --role="$role" --user_pass="$role"; \
       done \
    && wp rewrite structure --path=/src/src '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > /src/src/.htaccess \
    && mkdir -p /src/src/wp-content/uploads \
    && chown -R www-data:www-data /src/src/wp-content/uploads \
    && wp option get --path=/src/src siteurl \
    && wp user list --path=/src/src --fields=user_login,roles \
    && wp-stop

# Configure the PHPUnit suite against the test database.
RUN sed -e "s/youremptytestdbnamehere/wordpress_test/" \
        -e "s/yourusernamehere/wordpress/" \
        -e "s/yourpasswordhere/wordpress/" \
        -e "s/'localhost'/'127.0.0.1'/" \
        wp-tests-config-sample.php > wp-tests-config.php

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --group kses || echo "WARNING: phpunit reported failures") \
    && wp-stop
