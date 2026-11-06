# Square for WooCommerce (woocommerce-square), scanned as a plugin inside a working WooCommerce store.
#
# /src                        the woocommerce-square checkout (the repository named in project.yaml), with Composer
#                             and npm dependencies installed and assets built (build/)
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/woocommerce-square
# /tmp/wordpress              a second WordPress + WooCommerce copy used only by the PHPUnit suite
# /tmp/wordpress-tests-lib    the WordPress PHPUnit test library
# /woocommerce                a symlink to the WooCommerce copy in /tmp/wordpress: tests/php/bootstrap.php loads
#                             WooCommerce from ../woocommerce/woocommerce.php next to the plugin root, which for
#                             /src is /woocommerce
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
#
# The repository's CI lints on PHP 7.4 and has no PHPUnit job; the plugin header declares PHP 7.4 to 8.4 and
# phpcs-compat.xml.dist checks 7.4-8.4, so the image builds on 8.3 like the other WooCommerce enrollments.
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

# Node 20 and npm for the asset build (package.json engines: node >=20, npm >=10; .nvmrc v20).
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
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

# scanner contract: the woocommerce-square checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as `npm run build:dev` does (composer install, then the webpack build into build/), minus the
# .pot file and the release zip that `npm run build` adds. Composer installs dev packages too: PHPUnit lives there.
# Do not pass --classmap-authoritative: woocommerce-square.php registers the plugin namespace with addPsr4() at
# runtime, which an authoritative classmap ignores. package.json has no install scripts; the variable keeps
# Playwright (a devDependency) from fetching browsers should that change.
RUN PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --no-audit --no-fund \
    && composer install --no-progress \
    && npm run build:webpack \
    && test -f /src/build/index.js && test -f /src/build/settings.asset.php \
    && test -f /src/build/assets/frontend/wc-square.js && test -d /src/build/images \
    && test -f /src/vendor/autoload.php && test -x /src/vendor/bin/phpunit

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created, manages orders and products)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   (anonymous)                   no login; guest checkout is enabled
# The store is a US store in USD, as bin/docker-setup.sh configures it, because Square requires the store country
# and currency to match the connected Square account. No Square account is connected and there is no network
# during the scan, so the Square gateways stay unconfigured. The site is in development mode
# (WP_ENVIRONMENT_TYPE=development).
# A second, empty database, square_tests, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE square_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON square_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Square for WooCommerce" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/woocommerce-square" \
    && wp plugin activate woocommerce-square --path="$WP_ROOT" \
    && wp user create --path="$WP_ROOT" shopmanager shopmanager@example.com --role=shop_manager --user_pass=shopmanager \
    && wp user create --path="$WP_ROOT" customer customer@example.com --role=customer --user_pass=customer \
    && wp option update --path="$WP_ROOT" woocommerce_store_address "60 29th Street" \
    && wp option update --path="$WP_ROOT" woocommerce_store_city "San Francisco" \
    && wp option update --path="$WP_ROOT" woocommerce_default_country "US:CA" \
    && wp option update --path="$WP_ROOT" woocommerce_store_postcode "94110" \
    && wp option update --path="$WP_ROOT" woocommerce_currency "USD" \
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

# PHPUnit: install the test library and a second WordPress copy under /tmp, against square_tests (the database
# already exists, so the last argument skips creation). tests/php/bootstrap.php loads WooCommerce from
# ../woocommerce/woocommerce.php relative to the plugin root, so copy the WooCommerce the live site installed into
# the test copy's plugins directory and point /woocommerce at it.
RUN wp-start \
    && bash tests/php/bin/install-wp-tests.sh square_tests wordpress wordpress 127.0.0.1 latest true \
    && cp -a "$WP_ROOT/wp-content/plugins/woocommerce" /tmp/wordpress/wp-content/plugins/woocommerce \
    && ln -s /tmp/wordpress/wp-content/plugins/woocommerce /woocommerce \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --configuration tests/php/phpunit.xml.dist --filter 'Error_Classification_Test' \
          || echo "WARNING: phpunit reported failures") \
    && wp-stop
