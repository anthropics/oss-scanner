# ActivityPub plugin for WordPress.
#
# /src                       the wordpress-activitypub checkout (the repository named in project.yaml), with its
#                            Composer dev dependencies installed. Its built JavaScript (build/) is committed, so no
#                            asset build is needed.
# /var/www/html              a WordPress release install that Apache serves; the plugin is symlinked into
#                            wp-content/plugins/activitypub, so a patch to /src takes effect on the next request
# /opt/wordpress-tests-lib   the WordPress PHPUnit test library the plugin's suite runs against
#
# The site is served by Apache with mod_rewrite and AllowOverride All. The database is MariaDB. Start both with
# `wp-start`; the site listens on http://127.0.0.1/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_TESTS_DIR=/opt/wordpress-tests-lib \
    WP_CORE_DIR=/opt/wordpress-tests-core

# mysqli is the extension WordPress uses; the rest are the ones the WordPress hosting handbook recommends. subversion
# fetches the WordPress test library.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP: errors are logged, not shown; OPcache picks up edited files immediately.
RUN { echo 'memory_limit=256M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/dev/stderr'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

RUN a2enmod rewrite headers \
    && printf '<Directory /var/www/html>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
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

# scanner contract: the plugin checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# PHP dev dependencies: PHPUnit, yoast/phpunit-polyfills, PHPCS with the WordPress standards, PHPStan.
RUN composer install --no-progress

# A working single-site WordPress with the plugin active, pretty permalinks (as the project's wp-env uses), and one
# user per default role for access-control reproductions (password = username):
#   admin, editor, author, contributor, subscriber
# A second, empty database, wordpress_test, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE wordpress_test; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON wordpress_test.* TO 'wordpress'@'%';" \
    && wp core download --path=/var/www/html \
    && wp config create --path=/var/www/html --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp core install --path=/var/www/html --url=http://127.0.0.1 --title="OSS Scanner ActivityPub" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for role in editor author contributor subscriber; do \
         wp user create --path=/var/www/html "$role" "$role@example.com" --role="$role" --user_pass="$role"; \
       done \
    && ln -s /src /var/www/html/wp-content/plugins/activitypub \
    && wp plugin activate --path=/var/www/html activitypub \
    && wp rewrite structure --path=/var/www/html '/%year%/%monthnum%/%postname%/' --hard \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > /var/www/html/.htaccess \
    && mkdir -p /var/www/html/wp-content/uploads \
    && chown -R www-data:www-data /var/www/html/wp-content/uploads \
    && wp plugin list --path=/var/www/html --fields=name,status,version \
    && wp user list --path=/var/www/html --fields=user_login,roles \
    && wp-stop

# The WordPress PHPUnit test library, installed by the plugin's own script against the test database. The last argument
# skips creating the database, which exists already.
RUN wp-start \
    && bin/install-wp-tests.sh wordpress_test wordpress wordpress 127.0.0.1 latest true \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --filter 'Test_Signature|Test_Inbox_Controller' || echo "WARNING: phpunit reported failures") \
    && wp-stop
