# WooCommerce PayPal Payments (woocommerce-paypal-payments), scanned as a plugin inside a working WooCommerce
# store.
#
# /src                        the woocommerce-paypal-payments checkout (the repository named in project.yaml), with
#                             Composer and npm dependencies installed and the webpack assets built (assets/). This is
#                             the development layout the maintainers' DDEV stack uses: vendor/ is not prefixed by
#                             PHP-Scoper as it is in the release zip, and lib/packages/ holds the committed,
#                             Mozart-prefixed copies of inpsyde/modularity and psr/container the plugin boots with.
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/woocommerce-paypal-payments
# /tmp/wordpress              a second WordPress + WooCommerce copy, with the plugin active, used only by the
#                             integration PHPUnit suite (tests/integration); the unit suite (tests/PHPUnit) runs on
#                             Brain Monkey and needs no WordPress at all
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
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 22 and npm for the asset build: the release workflow (.github/workflows/build-and-distribute.yml) and the
# maintainers' DDEV config (.ddev/config.yaml) build with Node 22; there is no .nvmrc or engines field.
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
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
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop

# scanner contract: the woocommerce-paypal-payments checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as the maintainers' DDEV `orchestrate` command does (composer install, npm ci, npm run build),
# with one difference: @inpsyde/playwright-utils, a devDependency used only by the Playwright end-to-end suite, is
# published on GitHub Packages (npm.pkg.github.com, see .npmrc), which refuses anonymous downloads. It is removed
# from package.json and package-lock.json for the install, and both files are put back afterwards so /src matches
# the repository. --ignore-scripts skips npm lifecycle scripts (none are needed for the build). Composer installs
# the dev packages too: PHPUnit, Brain Monkey and the WordPress and WooCommerce stubs live there, and
# wikimedia/composer-merge-plugin folds every modules/*/composer.json autoloader into vendor/autoload.php.
RUN cp package.json /tmp/package.json.orig && cp package-lock.json /tmp/package-lock.json.orig \
    && node -e 'const fs = require("fs"); const p = "@inpsyde/playwright-utils"; \
         const pkg = JSON.parse(fs.readFileSync("package.json")); delete pkg.devDependencies[p]; \
         fs.writeFileSync("package.json", JSON.stringify(pkg, null, 2)); \
         const lock = JSON.parse(fs.readFileSync("package-lock.json")); delete lock.packages[""].devDependencies[p]; \
         for (const k of Object.keys(lock.packages)) if (k.startsWith("node_modules/" + p)) delete lock.packages[k]; \
         fs.writeFileSync("package-lock.json", JSON.stringify(lock, null, 2));' \
    && npm ci --ignore-scripts --no-audit --no-fund \
    && mv /tmp/package.json.orig package.json && mv /tmp/package-lock.json.orig package-lock.json \
    && composer install --prefer-dist --no-progress \
    && npm run build \
    && test -d /src/vendor && test -d /src/node_modules \
    && test -f /src/assets/ppcp-button-js-button.js && test -f /src/assets/ppcp-settings-js-index.js

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created, manages orders and products)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   (anonymous)                   no login; guest checkout is enabled
# The site is in development mode (WP_ENVIRONMENT_TYPE=development). The store is not connected to PayPal: no
# client id, secret or merchant id is configured (the plugin's settings offer a sandbox mode), and there is no
# network during the scan. A second, empty database, ppcp_tests, is for the integration PHPUnit suite's own
# WordPress copy below.
# The wordpress.org downloads are retried, because a truncated transfer ("cURL error 18") aborted one build; a
# `for` loop exits 0 whatever the last attempt did, so each one is followed by an explicit check.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE ppcp_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON ppcp_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && for i in 1 2 3; do wp core download --path="$WP_ROOT" --force && break; sleep 10; done \
    && test -f "$WP_ROOT/wp-settings.php" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner WooCommerce PayPal Payments" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for i in 1 2 3; do wp plugin install woocommerce --force --activate --path="$WP_ROOT" && break; sleep 10; done \
    && wp plugin is-active woocommerce --path="$WP_ROOT" \
    && for i in 1 2 3; do wp theme install storefront --force --activate --path="$WP_ROOT" && break; sleep 10; done \
    && test "$(wp theme list --status=active --field=name --path="$WP_ROOT")" = storefront \
    && ln -s /src "$WP_ROOT/wp-content/plugins/woocommerce-paypal-payments" \
    && wp plugin activate woocommerce-paypal-payments --path="$WP_ROOT" \
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

# PHPUnit integration suite (tests/integration): the maintainers run it against a real WordPress + WooCommerce
# site (their DDEV site; .github/workflows/integration.yml runs `ddev orchestrate`, then setup.php, then PHPUnit).
# Here that site is a second copy under /tmp/wordpress on the ppcp_tests database, with the plugin symlinked in
# and active, and .env.integration (gitignored) points PPCP_INTEGRATION_WP_DIR at it so the suite never touches
# the Apache site. setup.php seeds the tax options and tests/integration/data/tax_rates.csv the totals tests rely
# on. WooCommerce Subscriptions, which CI installs from a private Composer mirror, is not available here, so the
# tests that need it (tests/integration/PHPUnit/PayPalSubscriptions/) fail for that reason only.
RUN wp-start \
    && for i in 1 2 3; do wp core download --path=/tmp/wordpress --force && break; sleep 10; done \
    && test -f /tmp/wordpress/wp-settings.php \
    && wp config create --path=/tmp/wordpress --dbname=ppcp_tests --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp core install --path=/tmp/wordpress --url=http://127.0.0.1:8080 --title="PPCP integration tests" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for i in 1 2 3; do wp plugin install woocommerce --force --activate --path=/tmp/wordpress && break; sleep 10; done \
    && wp plugin is-active woocommerce --path=/tmp/wordpress \
    && ln -s /src /tmp/wordpress/wp-content/plugins/woocommerce-paypal-payments \
    && wp plugin activate woocommerce-paypal-payments --path=/tmp/wordpress \
    && wp user create --path=/tmp/wordpress customer customer@example.com --role=customer --user_pass=password \
    && wp wc tool run install_pages --user=admin --path=/tmp/wordpress \
    && printf 'PPCP_INTEGRATION_WP_DIR=/tmp/wordpress\n' > /src/.env.integration \
    && php tests/integration/PHPUnit/setup.php \
    && wp-stop

# Run a small slice of both PHPUnit suites so you know the image works, but do not let a failing test abort the
# build: the unit suite needs no services, the integration suite needs MariaDB.
RUN (vendor/bin/phpunit --configuration phpunit.xml.dist --filter 'Helper' || echo "WARNING: phpunit reported failures") \
    && wp-start \
    && (vendor/bin/phpunit --configuration tests/integration/phpunit.xml.dist --filter 'Helper' \
         || echo "WARNING: phpunit (integration) reported failures") \
    && wp-stop
