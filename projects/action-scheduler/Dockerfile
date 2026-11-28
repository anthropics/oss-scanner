# Action Scheduler (action-scheduler), a background job queue library for WordPress, scanned both as the standalone
# plugin it ships as on wordpress.org and as the copy a working WooCommerce store runs. WooCommerce bundles its own
# copy of this library under wp-content/plugins/woocommerce/packages/action-scheduler; at runtime the
# ActionScheduler_Versions registry loads the newest registered copy (ties go to the copy that loaded first, and
# wp-content/plugins/action-scheduler sorts before woocommerce), so the build asserts that the copy that initializes
# is /src and the scanner exercises this checkout with WooCommerce as its main consumer.
#
# /src                        the action-scheduler checkout (the repository named in project.yaml), with Composer
#                             dependencies installed: PHPUnit and its polyfills for the suite, wp-cli/wp-cli for the
#                             WP-CLI command tests, the coding-standard sniffs. There is no asset build and no Node:
#                             package.json's only script makes the release zip, and package-lock.json lists no packages.
# /var/www/html               the WordPress install Apache serves, with WooCommerce and Storefront from wordpress.org
#                             and /src symlinked in as wp-content/plugins/action-scheduler
# /tmp/wordpress              a second WordPress copy used only by the PHPUnit suite
# /tmp/wordpress-tests-lib    the WordPress PHPUnit test library
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
# PHP 8.3 is the newest version the repository's CI matrix tests (.github/workflows/pr-unit-tests.yml: 7.2 to 8.3).
FROM php:8.3-apache-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html \
    WP_PLUGIN_DIR=/tmp/plugins

# WP_PLUGIN_DIR is read only by tests/bootstrap.php. Without it the suite derives the plugins directory from the
# directory above the checkout, which is / for a checkout at /src, and the migration tests that compute plugin
# basenames from it fail. The PHPUnit step below links /src into it as /tmp/plugins/src, the plugin the bootstrap
# activates, so the test copy of WordPress loads the checkout from inside its plugins directory as CI does.
# WordPress does not read the variable, so the Apache site and WP-CLI are unaffected.

# Subversion is for tests/bin/install.sh, which exports the WordPress test library from develop.svn.wordpress.org.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps subversion mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# WP-CLI, for setting up content, users and options in reproductions, and for the library's own
# `wp action-scheduler ...` commands.
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

# scanner contract: the action-scheduler checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install the Composer dependencies as the repository's CI does (`composer install --prefer-dist` in
# .github/workflows/pr-unit-tests.yml), dev packages included: PHPUnit 8.5 and the Yoast polyfills run the suite,
# wp-cli/wp-cli provides the classes the WP-CLI command tests need, woocommerce-sniffs and phpcs-changed are the
# linters. composer.json pins the Composer platform to PHP 7.2, so the lock file resolves here as it does in CI.
RUN composer install --prefer-dist --no-progress \
    && test -d /src/vendor && test -x /src/vendor/bin/phpunit

# Install a working single-site WordPress + WooCommerce on MariaDB, with one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted; Tools > Scheduled Actions needs manage_options)
#   shopmanager / shopmanager     shop_manager  (admin-created; WooCommerce > Status > Scheduled Actions needs
#                                               manage_woocommerce, so this role reaches the same list table)
#   customer / customer           customer      (self-registerable; registration is enabled below)
#   subscriber / subscriber       subscriber    (the lowest WordPress role, no screen of this library)
#   (anonymous)                   no login; guest checkout is enabled
# /src is activated as the plugin wp-content/plugins/action-scheduler next to WooCommerce, and the build asserts that
# the copy ActionScheduler_Versions initialized is the one in /src, not the copy bundled inside WooCommerce. Three
# pending sample actions in the `oss-scanner` group give the admin screen rows from the start. There is no network
# during the scan; WP-Cron and the async queue runner only talk to 127.0.0.1.
# A second, empty database, as_tests, is for the PHPUnit suite, which drops and recreates its tables.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE as_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON as_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Action Scheduler" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/action-scheduler" \
    && wp plugin activate action-scheduler --path="$WP_ROOT" \
    && wp eval --path="$WP_ROOT" 'echo "Action Scheduler ", ActionScheduler_Versions::instance()->latest_version(), " from ", ( new ReflectionClass( "ActionScheduler" ) )->getFileName(), "; registered: ", implode( ", ", array_keys( ActionScheduler_Versions::instance()->get_versions() ) ), "\n";' \
    && wp eval --path="$WP_ROOT" 'echo ( new ReflectionClass( "ActionScheduler" ) )->getFileName();' | grep -q '^/src/classes/abstracts/ActionScheduler.php$' \
    && wp user create --path="$WP_ROOT" shopmanager shopmanager@example.com --role=shop_manager --user_pass=shopmanager \
    && wp user create --path="$WP_ROOT" customer customer@example.com --role=customer --user_pass=customer \
    && wp user create --path="$WP_ROOT" subscriber subscriber@example.com --role=subscriber --user_pass=subscriber \
    && wp option update --path="$WP_ROOT" woocommerce_coming_soon no \
    && wp option update --path="$WP_ROOT" woocommerce_enable_guest_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_signup_and_login_from_checkout yes \
    && wp option update --path="$WP_ROOT" woocommerce_enable_myaccount_registration yes \
    && wp wc tool run install_pages --user=admin --path="$WP_ROOT" \
    && wp wc product create --user=admin --path="$WP_ROOT" --name="Scan product" --regular_price=10 --type=simple \
    && wp action-scheduler action generate oss_scanner_sample_hook tomorrow --count=3 --interval=3600 \
         --args='{"order_id":1,"note":"sample"}' --group=oss-scanner --path="$WP_ROOT" \
    && wp action-scheduler action list --status=pending --group=oss-scanner --path="$WP_ROOT" \
    && wp action-scheduler status --path="$WP_ROOT" \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && mkdir -p "$WP_ROOT/wp-content/uploads" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin list --path="$WP_ROOT" --status=active --fields=name,version \
    && wp-stop

# PHPUnit: install the WordPress test library and a second WordPress copy under /tmp, against as_tests, with the
# repository's own script and the arguments CI passes (.github/workflows/pr-unit-tests.yml). The database already
# exists, so the last argument skips creation. tests/bootstrap.php finds the library at /tmp/wordpress-tests-lib.
RUN mkdir -p "$WP_PLUGIN_DIR" && ln -s /src "$WP_PLUGIN_DIR/src" \
    && wp-start \
    && tests/bin/install.sh as_tests wordpress wordpress 127.0.0.1 latest true \
    && test -f /tmp/wordpress-tests-lib/includes/bootstrap.php && test -f /tmp/wordpress/wp-settings.php \
    && wp-stop

# Run a small slice of the PHPUnit suite so you know the image works, but do not let a failing test abort the build.
RUN wp-start \
    && (vendor/bin/phpunit -c tests/phpunit.xml.dist --filter 'Schedule_Test' || echo "WARNING: phpunit reported failures") \
    && wp-stop
