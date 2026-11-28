# syntax=docker/dockerfile:1
# Public source at /src; WordPress/WooCommerce at /var/www/html; test WordPress under /tmp.
FROM php:8.3-apache-bookworm

# WP_TESTS_DIR and WP_CORE_DIR pin the PHPUnit layout above for bin/install-wp-tests.sh and tests/bootstrap.php,
# whatever TMPDIR is at run time.
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html \
    WP_TESTS_DIR=/tmp/wordpress-tests-lib \
    WP_CORE_DIR=/tmp/wordpress

# mysqli is what WordPress uses; the rest are the extensions the WordPress hosting handbook recommends.
# subversion: install-wp-tests.sh checks the test library out of develop.svn.wordpress.org.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev libonig-dev zip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath mbstring \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 24 and npm 11 match the plugin asset-build toolchain.
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP (php.ini-production values): errors are logged to /var/log/php-error.log, not shown, and not
# sent to stderr (PHPUnit turns stderr output of process-isolated tests into errors); output_buffering=4096 as in
# php.ini-production for Apache (the CLI SAPI always forces it to 0); OPcache picks up edited files immediately.
RUN { echo 'memory_limit=512M'; \
      echo 'upload_max_filesize=64M'; \
      echo 'post_max_size=64M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'error_log=/var/log/php-error.log'; \
      echo 'output_buffering=4096'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini \
    && touch /var/log/php-error.log && chmod 666 /var/log/php-error.log

# Apache serves /var/www/html with .htaccess enabled.
RUN a2enmod rewrite headers expires \
    && printf '<Directory /var/www/html>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\n' \
         > /etc/apache2/conf-available/wordpress.conf \
    && a2enconf wordpress

# wp-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'for attempt in $(seq 1 120); do mariadb-admin ping --silent 2>/dev/null && break; sleep 0.5; done' \
      'mariadb-admin ping --silent' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop


COPY . /src
WORKDIR /src

# Call webpack directly so npm prebuild does not remove PHPUnit and other dev dependencies.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && composer install --no-progress --optimize-autoloader \
    && NODE_ENV=production ./node_modules/.bin/wp-scripts build --webpack-src-dir=js/src \
    && test -s js/build/index.js && test -s vendor/autoload.php

RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE scanner_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON scanner_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Snapchat for WooCommerce" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/snapchat-for-woocommerce" \
    && wp plugin activate snapchat-for-woocommerce --path="$WP_ROOT" \
    && wp user create --path="$WP_ROOT" shopmanager shopmanager@example.com --role=shop_manager --user_pass=shopmanager \
    && wp user create --path="$WP_ROOT" customer customer@example.com --role=customer --user_pass=customer \
    && wp option update --path="$WP_ROOT" woocommerce_coming_soon no \
    && wp option update --path="$WP_ROOT" woocommerce_enable_guest_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_signup_and_login_from_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_myaccount_registration yes \
    && wp wc tool run install_pages --user=admin --path="$WP_ROOT" \
    && wp wc product create --user=admin --path="$WP_ROOT" --name="Scan product" --regular_price=10 --type=simple \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && mkdir -p "$WP_ROOT/wp-content/uploads" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin list --path="$WP_ROOT" --status=active --fields=name,version \
    && wp-stop


# Use the same released WP/Woo versions as the runtime and retain WooCommerce test helpers.
RUN wp_version="$(wp core version --path="$WP_ROOT")" \
    && wc_version="$(sed -n 's/^[[:space:]]*\* Version:[[:space:]]*//p' /var/www/html/wp-content/plugins/woocommerce/woocommerce.php | head -1 | tr -d '\r')" \
    && test -n "$wc_version" \
    && bash bin/install-wp-tests.sh scanner_tests wordpress wordpress 127.0.0.1 "$wp_version" "$wc_version" true \
    && printf "\ndefine( 'WP_TESTS_PHPUNIT_POLYFILLS_PATH', '/src/vendor/yoast/phpunit-polyfills' );\n" >> "$WP_TESTS_DIR/wp-tests-config.php"

RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-runtime-check.php <<'PHP'
<?php
if ( ! class_exists( 'SnapchatForWooCommerce\Config' ) ) {
    throw new RuntimeException( 'The target plugin did not load.' );
}
foreach ( array( 0, get_user_by( 'login', 'customer' )->ID ) as $user_id ) {
    wp_set_current_user( $user_id );
    $request = new WP_REST_Request( 'POST', '/wc/sfw/snapchat/settings' );
    $response = rest_do_request( $request );
    if ( ! in_array( $response->get_status(), array( 401, 403 ), true ) ) {
        throw new RuntimeException( 'Unprivileged settings request was not denied: ' . $response->get_status() );
    }
}
wp_set_current_user( get_user_by( 'login', 'shopmanager' )->ID );
$response = rest_do_request( new WP_REST_Request( 'GET', '/wc/sfw/snapchat/settings' ) );
if ( 200 !== $response->get_status() ) {
    throw new RuntimeException( 'Shop manager cannot read settings: ' . $response->get_status() );
}
echo "Plugin loaded; anonymous/customer writes denied; shop manager settings readable.\n";
PHP
cat > /usr/local/bin/scanner-test <<'TEST'
#!/bin/bash
set -euo pipefail
cd /src
wp-start
trap wp-stop EXIT
wp eval-file /usr/local/bin/scanner-runtime-check.php --path="$WP_ROOT" --user=admin
curl --fail --silent --show-error http://127.0.0.1/shop/ >/dev/null
vendor/bin/phpunit --configuration phpunit.xml.dist --fail-on-empty-test-suite
TEST
chmod +x /usr/local/bin/scanner-test
SH
