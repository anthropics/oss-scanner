# WooCommerce Payfast Gateway (woocommerce-gateway-payfast), scanned as a plugin inside a working WooCommerce
# store.
#
# /src                        the woocommerce-gateway-payfast checkout (the repository named in project.yaml), with
#                             the npm dependencies and Composer dev tooling installed and the Checkout block script
#                             built (build/payment-method.js)
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/woocommerce-gateway-payfast
#
# This repository has no PHPUnit suite: tests/ holds Playwright end-to-end tests that need a browser and a Payfast
# sandbox account, so there is no test library and no second WordPress copy in this image. The checks that run
# offline are the PHP compatibility and coding-standard sniffs (vendor/bin/phpcs) and WP-CLI against the store.
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.3-apache-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 24 and npm 11 for the asset build (package.json engines: node >=24.0.0, npm >=11.0.0; .nvmrc v24.15).
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
# sent to stderr; output_buffering=4096 as in php.ini-production for Apache (the CLI SAPI always forces it to 0);
# OPcache picks up edited files immediately.
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
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop

# scanner contract: the woocommerce-gateway-payfast checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as its README's quick start does: npm ci, composer install, npm run build:webpack. The production
# `npm run build` is not used because it also generates the .pot file and the release zip. --ignore-scripts keeps npm
# from running package lifecycle scripts; nothing the build needs depends on one. Composer brings only dev tooling
# (PHP_CodeSniffer with the WooCommerce and PHPCompatibility standards); the plugin has no runtime Composer packages.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && composer install --no-progress \
    && npm run build:webpack \
    && test -f /src/build/payment-method.js && test -f /src/build/payment-method.asset.php \
    && test -x /src/vendor/bin/phpcs

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created, manages orders and products)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   (anonymous)                   no login; guest checkout is enabled
# The store trades in South African rand (ZAR), the only currency the gateway accepts, and the gateway is enabled in
# its sandbox mode (the `testmode` setting, which also skips the ITN source-IP check) with placeholder credentials:
# they are not a Payfast account, they only make the gateway available at checkout and give the ITN signature a
# known passphrase. There is no network during the scan, so the redirect to Payfast and the plugin's calls to
# Payfast (validation of a notification, subscription charges) cannot complete; see threat_model.md.
# Saving the settings can trigger the plugin's credential check against api.payfast.co.za; the flag it may leave
# behind is removed so the placeholders do not disable the gateway. The uploads directory exists before WooCommerce
# is activated so that its setup can write its logs and placeholder images without warnings.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner WooCommerce Payfast" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && mkdir -p "$WP_ROOT/wp-content/uploads" && chown www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/woocommerce-gateway-payfast" \
    && wp plugin activate woocommerce-gateway-payfast --path="$WP_ROOT" \
    && wp user create --path="$WP_ROOT" shopmanager shopmanager@example.com --role=shop_manager --user_pass=shopmanager \
    && wp user create --path="$WP_ROOT" customer customer@example.com --role=customer --user_pass=customer \
    && wp option update --path="$WP_ROOT" woocommerce_currency ZAR \
    && wp option update --path="$WP_ROOT" woocommerce_default_country 'ZA:WC' \
    && wp option update --path="$WP_ROOT" woocommerce_coming_soon no \
    && wp option update --path="$WP_ROOT" woocommerce_enable_guest_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_signup_and_login_from_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_myaccount_registration yes \
    && wp option update --path="$WP_ROOT" woocommerce_payfast_settings --format=json \
         '{"enabled":"yes","title":"Payfast","testmode":"yes","merchant_id":"00000000","merchant_key":"scanner-merchant-key","pass_phrase":"scanner-passphrase"}' \
    && ( wp option delete --path="$WP_ROOT" woocommerce_payfast_invalid_credentials || true ) \
    && wp wc tool run install_pages --user=admin --path="$WP_ROOT" \
    && wp wc product create --user=admin --path="$WP_ROOT" --name="Scan product" --regular_price=100 --type=simple \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin list --path="$WP_ROOT" --status=active --fields=name,version \
    && wp eval --path="$WP_ROOT" 'exit( WC()->payment_gateways()->payment_gateways()["payfast"]->is_available() ? 0 : 1 );' \
    && wp-stop

# There is no PHPUnit suite. Run the PHP compatibility sniffs (PHP 7.4 to 8.4, the range CI checks) on the plugin's
# own files instead, so you know the tooling works; a sniff failure does not abort the build. The excludes mirror
# the repository's AGENTS.md: the ruleset itself scans everything under the current directory.
RUN (vendor/bin/phpcs -p --standard=phpcs-compat.xml.dist '--ignore=*/vendor/*,*/node_modules/*,*/build/*,*/tests/*' . \
     || echo "WARNING: phpcs reported issues")
