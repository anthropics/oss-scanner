# WooCommerce Tax, formerly WooCommerce Shipping & Tax (woocommerce-services), scanned as a plugin inside a working
# WooCommerce store.
#
# /src                        the woocommerce-services checkout (the repository named in project.yaml), with Composer
#                             and npm dependencies installed and the admin client bundle built into /src/dist
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/woocommerce-services
# /tmp/woocommerce            a WooCommerce source checkout at the store's version; the PHPUnit suite boots through
#                             its legacy test bootstrap (tests/php/bootstrap.php requires it)
# /tmp/wordpress              a second WordPress copy used only by the PHPUnit suite
# /tmp/wordpress-tests-lib    the WordPress PHPUnit test library
#
# The translations under i18n/ are not generated: they come from translate.wordpress.com at release time and the
# plugin falls back to English without them.
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.4-apache-bookworm

# COMPOSER_MAX_PARALLEL_HTTP=4: fewer simultaneous GitHub zipball downloads, which drop mid-transfer (curl error 18)
# on a slow link at Composer's default of 12. Both composer install steps below also retry up to three times.
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    COMPOSER_MAX_PARALLEL_HTTP=4 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html

# mysqli is what WordPress uses; the rest are the extensions the WordPress hosting handbook recommends.
# subversion: WooCommerce's tests/bin/install.sh checks the test library out of develop.svn.wordpress.org.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 24 and npm for the client build (package.json engines: node >=24; .nvmrc 24.21.0).
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
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop

# scanner contract: the woocommerce-services checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as its maintainers do (.github/workflows/build.yml and js_tests.yml), minus the release zip.
# The git:// rewrite is what CI does before npm ci: one dependency in npm-shrinkwrap.json is a git:// URL.
# --ignore-scripts skips husky's prepare hook and the Chromium download puppeteer's postinstall would run; nothing
# the build needs has an install script. Composer installs dev packages too: PHPUnit lives there, and
# vendor/autoload_packages.php (the Jetpack autoloader the plugin requires) is written by it. `npm run dist` is the
# production webpack build into dist/woocommerce-services-<version>.{js,css}.
RUN git config --global url.https://github.com/.insteadOf git://github.com/ \
    && npm ci --ignore-scripts --no-audit --no-fund \
    && for i in 1 2 3; do composer install --no-progress && break; [ "$i" = 3 ] && exit 1; sleep 15; done \
    && npm run dist \
    && test -f /src/vendor/autoload_packages.php && test -x /src/vendor/bin/phpunit \
    && test -n "$(ls /src/dist/woocommerce-services-*.js)" && test -n "$(ls /src/dist/woocommerce-services-*.css)"

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created, manages orders and products)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   (anonymous)                   no login; guest checkout is enabled
# The site is in development mode (WP_ENVIRONMENT_TYPE=development). The plugin loads its hooks and REST routes only
# when Jetpack is connected or in offline mode AND the terms of service are accepted (WC_Connect_Loader::pre_wc_init),
# so JETPACK_DEV_DEBUG puts Jetpack in offline mode and wc_connect_options records the acceptance, as the repository's
# own test environments do (tests/bin/install.sh, tests/e2e-playwright). The store is a US store with automated taxes
# turned on, so the tax lookup path is live. There is NO WordPress.com connection and no network during the scan:
# every request to the Connect Server (api.woocommerce.com) fails before it is sent, for want of a blog token.
# A second, empty database, wcs_tests, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE wcs_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON wcs_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp config set --path="$WP_ROOT" JETPACK_DEV_DEBUG true --raw \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner WooCommerce Tax" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && wp option update --path="$WP_ROOT" woocommerce_store_address "60 29th Street" \
    && wp option update --path="$WP_ROOT" woocommerce_store_city "San Francisco" \
    && wp option update --path="$WP_ROOT" woocommerce_default_country "US:CA" \
    && wp option update --path="$WP_ROOT" woocommerce_store_postcode "94110" \
    && wp option update --path="$WP_ROOT" woocommerce_currency "USD" \
    && wp option update --path="$WP_ROOT" woocommerce_weight_unit "lbs" \
    && wp option update --path="$WP_ROOT" woocommerce_dimension_unit "in" \
    && wp option update --path="$WP_ROOT" woocommerce_calc_taxes yes \
    && wp option update --path="$WP_ROOT" wc_connect_taxes_enabled yes \
    && wp option update --path="$WP_ROOT" wc_connect_options '{"tos_accepted":true}' --format=json \
    && ln -s /src "$WP_ROOT/wp-content/plugins/woocommerce-services" \
    && wp plugin activate woocommerce-services --path="$WP_ROOT" \
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

# PHPUnit, the way .github/workflows/php_tests.yml does it: the suite's bootstrap loads WooCommerce's own legacy test
# bootstrap from a WooCommerce source checkout under /tmp/woocommerce, so clone WooCommerce at the version the store
# runs, install its Composer packages (--no-scripts skips its post-install tooling step; the optimized autoloader it
# would have produced is dumped explicitly) and generate its feature config. WooCommerce's tests/bin/install.sh then
# installs the WordPress test library and a second WordPress copy under /tmp, against wcs_tests. The database already
# exists, so the last argument skips creation. The checkout's history is dropped to keep the image small.
RUN wp-start \
    && WC_VERSION="$(wp plugin get woocommerce --field=version --path="$WP_ROOT")" \
    && git clone --quiet --depth=1 --branch="$WC_VERSION" https://github.com/woocommerce/woocommerce.git /tmp/woocommerce \
    && rm -rf /tmp/woocommerce/.git \
    && for i in 1 2 3; do composer install --no-progress --no-scripts --working-dir=/tmp/woocommerce/plugins/woocommerce \
         && break; [ "$i" = 3 ] && exit 1; sleep 15; done \
    && composer dump-autoload --optimize --working-dir=/tmp/woocommerce/plugins/woocommerce \
    && php /tmp/woocommerce/plugins/woocommerce/bin/generate-feature-config.php \
    && test -f /tmp/woocommerce/plugins/woocommerce/tests/legacy/bootstrap.php \
    && test -f /tmp/woocommerce/plugins/woocommerce/vendor/yoast/phpunit-polyfills/phpunitpolyfills-autoload.php \
    && bash /tmp/woocommerce/plugins/woocommerce/tests/bin/install.sh wcs_tests wordpress wordpress 127.0.0.1 latest true \
    && test -f /tmp/wordpress-tests-lib/includes/functions.php \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --configuration phpunit.xml.dist --filter 'WP_Test_WC_Connect_Functions' || echo "WARNING: phpunit reported failures") \
    && wp-stop
