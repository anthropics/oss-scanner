# Google for WooCommerce (google-listings-and-ads), scanned as a plugin inside a working WooCommerce store.
#
# /src                        the google-listings-and-ads checkout (the repository named in project.yaml), with
#                             Composer dependencies installed and namespace-prefixed by the repository's own
#                             post-install scripts, npm dependencies installed, and the admin app built into
#                             /src/js/build (plus the translation template in /src/languages)
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/google-listings-and-ads
# /tmp/wordpress              a second WordPress copy used only by the PHPUnit suite, with a WooCommerce source
#                             checkout (the suite loads WooCommerce's test helpers from it) symlinked into its
#                             plugins directory
# /tmp/wordpress-tests-lib    the WordPress PHPUnit test library
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.4-apache-bookworm

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
# git: install-wp-tests.sh clones the WooCommerce monorepo at the current release tag for the test helpers.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 24 and npm 11 for the admin app build (.nvmrc v24; package.json engines: node ^24, npm ^11 || ^10 || ^9).
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

# scanner contract: the google-listings-and-ads checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as its CI does (.github/workflows/php-unit-tests.yml and build.yml), minus the release zip.
# `composer install` brings in PHPUnit (dev packages) and runs the repository's post-install-cmd scripts: it trims
# the Google API client to the services the plugin uses, removes unused Google Ads API versions, prefixes the
# vendored namespaces (bin/prefix-vendor-namespace.php) and regenerates the autoloader, so the vendor/ tree ends up
# exactly as shipped. npm's install scripts are skipped (nothing the build needs runs there) and `npm run build`
# runs without its pre and post scripts: the pre script is a second `composer install`, the post script zips a
# release. What remains is the production webpack build into js/build and the translation template. The npm and
# Composer download caches go at the end of the same step: they hold only what is already unpacked into
# node_modules and vendor, and they would otherwise add half a gigabyte to the layer.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && composer install --no-progress \
    && npm run build --ignore-scripts \
    && test -d /src/js/build && test -f /src/js/build/index.js && test -d /src/vendor \
    && test -f /src/languages/google-listings-and-ads.pot \
    && rm -rf /root/.npm /root/.composer/cache

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created, manages orders, products and this plugin)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   (anonymous)                   no login; guest checkout is enabled
# The site is in development mode (WP_ENVIRONMENT_TYPE=development). It has no Jetpack connection, so the plugin
# cannot reach the WooCommerce Connect Server, which is the only road to Google; there is no network during the
# scan anyway. The onboarding wizard therefore stops at the connection step, and everything behind it is driven
# through options, WP-CLI and PHPUnit mocks (see threat_model.md).
# A second, empty database, gla_tests, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE gla_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON gla_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Google for WooCommerce" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/google-listings-and-ads" \
    && wp plugin activate google-listings-and-ads --path="$WP_ROOT" \
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

# PHPUnit: install the test library and a second WordPress copy under /tmp, against gla_tests, exactly as
# php-unit-tests.yml does ("latest latest" = current WordPress and WooCommerce). The script downloads WordPress,
# clones the WooCommerce monorepo at the current release tag into /tmp/woocommerce-<version> (the suite needs
# WooCommerce's PHPUnit helpers, which the wordpress.org zip does not ship), runs `composer install --no-dev` in
# it, and checks the test library out of develop.svn.wordpress.org. The database already exists, so the last
# argument skips creation. The monorepo clone's .git directory is dropped afterwards: nothing reads it (the script
# marks the installed version with a file), and it only adds to the layer.
RUN wp-start \
    && bin/install-wp-tests.sh gla_tests wordpress wordpress 127.0.0.1 latest latest true \
    && rm -rf /tmp/woocommerce-*/.git \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit --configuration phpunit.xml.dist --filter 'Utility' || echo "WARNING: phpunit reported failures") \
    && wp-stop
