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

# Node and npm match the plugin asset-build toolchain.
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
      'for attempt in $(seq 1 120); do mariadb-admin ping --silent 2>/dev/null && break; sleep 0.5; done' \
      'mariadb-admin ping --silent' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/wp-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/wp-stop \
    && chmod +x /usr/local/bin/wp-start /usr/local/bin/wp-stop


ENV WC_DEVELOP_DIR=/tmp/woocommerce/plugins/woocommerce
RUN npm install --global pnpm@10.4.1
COPY . /src
WORKDIR /src
RUN pnpm install --frozen-lockfile --ignore-scripts \
    && composer install --no-progress --optimize-autoloader \
    && pnpm run uglify && pnpm run cleancss && pnpm run makepot \
    && test -s assets/js/admin.min.js

RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE DATABASE scanner_tests; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%'; GRANT ALL ON scanner_tests.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Customs Fees for WooCommerce" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && wp plugin install woocommerce --activate --path="$WP_ROOT" \
    && wp theme install storefront --activate --path="$WP_ROOT" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/customs-fees-for-woocommerce" \
    && wp plugin activate customs-fees-for-woocommerce --path="$WP_ROOT" \
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


# WooCommerce's real legacy test bootstrap is required by the plugin's suite.
RUN wc_version="$(sed -n 's/^[[:space:]]*\* Version:[[:space:]]*//p' "$WP_ROOT/wp-content/plugins/woocommerce/woocommerce.php" | head -1 | tr -d '\r')" \
    && test -n "$wc_version" \
    && git clone --depth 1 --branch "$wc_version" https://github.com/woocommerce/woocommerce.git /tmp/woocommerce \
    && composer install --working-dir="$WC_DEVELOP_DIR" --no-progress \
    && php "$WC_DEVELOP_DIR/bin/generate-feature-config.php" \
    && wp-start \
    && bash "$WC_DEVELOP_DIR/tests/bin/install.sh" scanner_tests wordpress wordpress 127.0.0.1 "$(wp core version --path="$WP_ROOT")" true \
    && wp-stop

RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-runtime-check.php <<'PHP'
<?php
if ( ! class_exists( 'CFWC_Calculator' ) ) {
    throw new RuntimeException( 'Customs Fees did not load.' );
}
update_option( 'cfwc_valuation_method', 'fob' );
update_option( 'cfwc_rules', array( array(
    'rule_id' => 'scan-flat', 'country' => 'CA', 'to_country' => 'CA',
    'from_country' => '', 'match_type' => 'all', 'type' => 'flat',
    'rate' => 0, 'amount' => 5, 'label' => 'Import Fee', 'taxable' => false,
    'tax_class' => '', 'valuation_method' => 'fob', 'base_includes' => array(),
    'stacking_mode' => 'add', 'priority' => 0,
) ) );
delete_transient( 'cfwc_rules_cache' );
if ( null === WC()->cart ) { wc_load_cart(); }
WC()->cart->empty_cart();
WC()->customer->set_shipping_country( 'CA' );
$product = new WC_Product_Simple();
$product->set_name( 'Scanner customs product' );
$product->set_regular_price( '50' );
$product->set_price( '50' );
$product->update_meta_data( '_cfwc_country_of_origin', 'CN' );
WC()->cart->add_to_cart( $product->save(), 1 );
$fees = ( new CFWC_Calculator() )->calculate_fees( WC()->cart );
$total = array_sum( array_column( $fees, 'amount' ) );
if ( 5.0 !== (float) $total ) {
    throw new RuntimeException( 'Expected a real customs fee of 5, got ' . $total );
}
echo "Real WooCommerce cart calculated a customs fee of 5.\n";
PHP
cat > /usr/local/bin/scanner-auth-check.php <<'PHP'
<?php
/** Exercise the actual admin-ajax endpoint with synthetic WordPress sessions. */
function scanner_ajax_request( $login, $valid_nonce ) {
    $headers = array();
    unset( $_COOKIE[ LOGGED_IN_COOKIE ] );
    wp_set_current_user( 0 );
    if ( null !== $login ) {
        $user = get_user_by( 'login', $login );
        $expires = time() + HOUR_IN_SECONDS;
        $token = WP_Session_Tokens::get_instance( $user->ID )->create( $expires );
        $auth = wp_generate_auth_cookie( $user->ID, $expires, 'auth', $token );
        $logged_in = wp_generate_auth_cookie( $user->ID, $expires, 'logged_in', $token );
        $_COOKIE[ LOGGED_IN_COOKIE ] = $logged_in;
        wp_set_current_user( $user->ID );
        $headers['Cookie'] = AUTH_COOKIE . '=' . $auth . '; ' . LOGGED_IN_COOKIE . '=' . $logged_in;
    }
    $response = wp_remote_post( admin_url( 'admin-ajax.php' ), array(
        'timeout' => 15,
        'headers' => $headers,
        'body' => array(
            'action' => 'cfwc_apply_template',
            'nonce' => $valid_nonce ? wp_create_nonce( 'cfwc_admin_nonce' ) : 'invalid',
            'template_id' => 'us_general',
            'append' => 'false',
        ),
    ) );
    if ( is_wp_error( $response ) ) {
        throw new RuntimeException( $response->get_error_message() );
    }
    return array( wp_remote_retrieve_response_code( $response ), trim( wp_remote_retrieve_body( $response ) ) );
}
$original_rules = get_option( 'cfwc_rules', array() );
foreach ( array( array( null, true, '0' ), array( 'customer', true, '-1' ), array( 'admin', false, '-1' ) ) as $case ) {
    list( $status, $body ) = scanner_ajax_request( $case[0], $case[1] );
    // This WordPress HTTP stack exposes the anonymous literal '0' body as empty.
    $denied = null === $case[0]
        ? 400 === $status && in_array( $body, array( '', '0' ), true )
        : in_array( $status, array( 200, 403 ), true ) && '-1' === $body;
    if ( ! $denied ) {
        throw new RuntimeException( 'Expected AJAX denial for ' . ( $case[0] ?? 'anonymous' ) . ': ' . $status . ' ' . $body );
    }
    wp_cache_delete( 'cfwc_rules', 'options' );
    wp_cache_delete( 'alloptions', 'options' );
    if ( $original_rules !== get_option( 'cfwc_rules', array() ) ) {
        throw new RuntimeException( 'Denied request changed rules.' );
    }
}
list( $status, $body ) = scanner_ajax_request( 'shopmanager', true );
$data = json_decode( $body, true );
if ( 200 !== $status || true !== ( $data['success'] ?? false ) ) {
    throw new RuntimeException( 'Shop manager could not apply a preset: ' . $status . ' ' . $body );
}
wp_cache_delete( 'cfwc_rules', 'options' );
wp_cache_delete( 'alloptions', 'options' );
$rules = get_option( 'cfwc_rules', array() );
if ( empty( $rules ) || $rules !== ( $data['data']['rules'] ?? null ) || 'US' !== $rules[0]['to_country'] || 10.0 !== (float) $rules[0]['rate'] ) {
    throw new RuntimeException( 'Successful AJAX request did not persist the rule.' );
}
update_option( 'cfwc_rules', $original_rules );
CFWC_Calculator::clear_cache();
echo "Anonymous/customer AJAX denied; bad nonce denied; shop manager preset application persisted.\n";
PHP
cat > /usr/local/bin/scanner-test <<'TEST'
#!/bin/bash
set -euo pipefail
cd /src
wp-start
trap wp-stop EXIT
wp eval-file /usr/local/bin/scanner-runtime-check.php --path="$WP_ROOT" --user=admin
wp eval-file /usr/local/bin/scanner-auth-check.php --path="$WP_ROOT" --user=admin
curl --fail --silent --show-error http://127.0.0.1/shop/ >/dev/null
# The repository's composer test wrapper masks failures; invoke PHPUnit directly.
vendor/bin/phpunit --configuration phpunit.xml.dist --fail-on-empty-test-suite
TEST
chmod +x /usr/local/bin/scanner-test
SH
