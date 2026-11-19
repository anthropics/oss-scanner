# WooCommerce core, scanned as the plugin inside a working WordPress site.
#
# /src                        the woocommerce monorepo checkout (the repository named in project.yaml), with pnpm
#                             and Composer dependencies installed and the plugin's assets built by
#                             `pnpm --filter=@woocommerce/plugin-woocommerce build`
# /src/plugins/woocommerce    the plugin itself; Apache serves it through a symlink at
#                             /var/www/html/wp-content/plugins/woocommerce
# /var/www/html               the WordPress install Apache serves, with Storefront from wordpress.org
# /tmp/wordpress              a second WordPress copy used only by the PHPUnit suite
# /tmp/wordpress-tests-lib    the WordPress PHPUnit test library
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.3-apache-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html \
    NODE_OPTIONS=--max-old-space-size=4096 \
    BROWSERSLIST_IGNORE_OLD_DATA=true \
    CI=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 24 and the pinned pnpm (root package.json: packageManager pnpm@10.33.0, engines node ^24.15.0).
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g pnpm@10.33.0 \
    && node --version && pnpm --version

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

# scanner contract: the woocommerce monorepo checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install the plugin and its workspace dependencies the way the repository's CI does
# (.github/actions/setup-woocommerce-monorepo, build-type "full"). Needs the network.
RUN pnpm install --filter='@woocommerce/plugin-woocommerce...' --frozen-lockfile

# Build. CI runs `pnpm --filter='@woocommerce/plugin-woocommerce...' build`, which runs the plugin's webpack builds
# (admin, blocks, classic assets) in parallel and needs more than 8 GB. The same builds run here one at a time:
# first the workspace packages the plugin depends on, then each of the plugin's build projects, so peak memory
# stays under 8 GB and the image also builds on a small machine. `build:project:packages` is the
# `composer install` in plugins/woocommerce. This is the slow step (15 to 30 minutes).
RUN pnpm --filter='@woocommerce/plugin-woocommerce^...' --workspace-concurrency=1 build \
    && for project in packages classic-assets admin blocks admin-screens actualize-translation-domains; do \
         pnpm --filter='@woocommerce/plugin-woocommerce' "build:project:$project" || exit 1; \
       done \
    && test -d /src/plugins/woocommerce/vendor

# Install a working single-site WordPress on MariaDB with WooCommerce from /src, and one user per role that matters
# for access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   shopmanager / shopmanager     shop_manager  (admin-created; manages products, orders, coupons, customers)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   editor / editor, author / author, contributor / contributor, subscriber / subscriber   WordPress default roles
#   (anonymous)                   no login; guest checkout is enabled
# A second, empty database, woocommerce_tests, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE woocommerce_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON woocommerce_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner WooCommerce" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && ln -s /src/plugins/woocommerce "$WP_ROOT/wp-content/plugins/woocommerce" \
    && wp plugin activate woocommerce --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && wp user create --path="$WP_ROOT" shopmanager shopmanager@example.com --role=shop_manager --user_pass=shopmanager \
    && wp user create --path="$WP_ROOT" customer customer@example.com --role=customer --user_pass=customer \
    && for role in editor author contributor subscriber; do \
         wp user create --path="$WP_ROOT" "$role" "$role@example.com" --role="$role" --user_pass="$role"; \
       done \
    && wp option update --path="$WP_ROOT" woocommerce_coming_soon no \
    && wp option update --path="$WP_ROOT" woocommerce_enable_guest_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_signup_and_login_from_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_myaccount_registration yes \
    && wp wc tool run install_pages --user=admin --path="$WP_ROOT" \
    && wp wc product create --user=admin --path="$WP_ROOT" --name="Scan product" --regular_price=10 --type=simple \
    && wp wc product create --user=admin --path="$WP_ROOT" --name="Scan download" --regular_price=5 --type=simple --virtual=true --downloadable=true \
    && wp wc payment_gateway update cod --user=admin --path="$WP_ROOT" --enabled=true \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && mkdir -p "$WP_ROOT/wp-content/uploads" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin list --path="$WP_ROOT" --status=active --fields=name,version \
    && wp-stop

# PHPUnit: install the test library and a second WordPress copy under /tmp, against woocommerce_tests, and place
# the CSV fixture one importer test reads from /var/www/sample.csv (see tests/php/bin/test-env-setup.sh).
# The maintainers run the suite in wp-env with the settings in plugins/woocommerce/.wp-env.test.json: WP_DEBUG off and
# WP_TESTS_DOMAIN=localhost. The generated wp-tests-config.php defaults to WP_DEBUG on, under which wc_setcookie()
# raises a notice in every test that sets a session cookie (headers are always "sent" in the CLI), so mirror CI here.
RUN wp-start \
    && cd /src/plugins/woocommerce \
    && tests/bin/install.sh woocommerce_tests wordpress wordpress 127.0.0.1 latest true \
    && sed -i -e "s/define( 'WP_DEBUG', true );/define( 'WP_DEBUG', false );/" \
              -e "s/define( 'WP_TESTS_DOMAIN', 'example.org' );/define( 'WP_TESTS_DOMAIN', 'localhost' );/" \
              /tmp/wordpress-tests-lib/wp-tests-config.php \
    && grep -E "WP_DEBUG|WP_TESTS_DOMAIN" /tmp/wordpress-tests-lib/wp-tests-config.php \
    && cp tests/legacy/unit-tests/importer/sample.csv /var/www/sample.csv \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && cd /src/plugins/woocommerce \
    && (sh ./client/blocks/bin/copy-blocks-json.sh && vendor/bin/phpunit -c ./phpunit.xml --filter 'WC_Tests_Formatting_Functions' \
        || echo "WARNING: phpunit reported failures") \
    && wp-stop
