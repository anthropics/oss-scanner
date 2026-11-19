# syntax=docker/dockerfile:1
# Secure Custom Fields (SCF), scanned as a plugin inside a working WordPress site.
#
# /src            the secure-custom-fields checkout (the repository named in project.yaml), with Composer (dev
#                 included) and npm dependencies installed and assets built into assets/build/
# /src/wordpress  the WordPress copy WorDBless loads for the PHPUnit suite (no database needed)
# /var/www/html   the WordPress install Apache serves, with /src symlinked in as
#                 wp-content/plugins/secure-custom-fields
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.4-apache-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1 \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html

# mysqli is what WordPress uses; the rest are the extensions the WordPress hosting handbook recommends.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev zip \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node 22 and npm for the asset build (.nvmrc: 22; package.json engines: node >=20.15.1, npm >=10.8.1).
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP (php.ini-production values): errors are logged to /var/log/php-error.log, not shown;
# output_buffering=4096 as in php.ini-production for Apache; OPcache picks up edited files immediately.
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

# scanner contract: the secure-custom-fields checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the plugin as its maintainers do. --ignore-scripts skips the husky `prepare` hook; Composer keeps dev
# packages (PHPUnit, WorDBless and the WordPress copy it installs at /src/wordpress).
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && composer install --no-progress \
    && npm run build \
    && test -s vendor/autoload.php && test -f wordpress/wp-settings.php \
    && ls assets/build/js/*.min.js >/dev/null

# Install a working single-site WordPress on MariaDB with SCF active and one user per role that matters for
# access-control reproductions:
#   admin / admin                 administrator (fully trusted)
#   editor / editor               editor        (unfiltered_html on single site)
#   author / author               author        (publishes own posts, uploads files)
#   contributor / contributor     contributor   (writes but cannot publish posts, no unfiltered_html)
#   subscriber / subscriber       subscriber    (self-registerable; registration is enabled below)
#   (anonymous)                   no login
# A field group "Scanner fields" (group_scanner) is attached to posts and exposed in the REST API, and the
# post "Scanner post" carries values for it.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp config set --path="$WP_ROOT" WP_ENVIRONMENT_TYPE development \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Secure Custom Fields" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && ln -s /src "$WP_ROOT/wp-content/plugins/secure-custom-fields" \
    && wp plugin activate secure-custom-fields --path="$WP_ROOT" \
    && for role in editor author contributor subscriber; do \
         wp user create --path="$WP_ROOT" "$role" "$role@example.com" --role="$role" --user_pass="$role" || exit 1; \
       done \
    && wp option update --path="$WP_ROOT" users_can_register 1 \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && mkdir -p "$WP_ROOT/wp-content/uploads" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp-stop

RUN <<'SH'
set -eu
cat > /usr/local/bin/scanner-seed.php <<'PHP'
<?php
$fields = array();
foreach ( array( 'text', 'textarea', 'wysiwyg', 'url', 'link', 'image', 'file', 'gallery', 'oembed', 'select',
	'post_object', 'relationship', 'page_link', 'taxonomy', 'user' ) as $type ) {
	$field = array( 'key' => "field_scanner_$type", 'label' => ucfirst( $type ), 'name' => "scanner_$type", 'type' => $type );
	if ( in_array( $type, array( 'select', 'post_object', 'user' ), true ) ) {
		$field['ui']   = 1;
		$field['ajax'] = 1;
	}
	if ( 'select' === $type ) {
		$field['choices'] = array( 'one' => 'One', 'two' => 'Two' );
	}
	$fields[] = $field;
}
$fields[] = array(
	'key' => 'field_scanner_repeater', 'label' => 'Repeater', 'name' => 'scanner_repeater', 'type' => 'repeater',
	'sub_fields' => array( array( 'key' => 'field_scanner_repeater_text', 'label' => 'Row text', 'name' => 'row_text', 'type' => 'text' ) ),
);
$fields[] = array(
	'key' => 'field_scanner_flexible', 'label' => 'Flexible', 'name' => 'scanner_flexible', 'type' => 'flexible_content',
	'layouts' => array( 'layout_scanner' => array( 'key' => 'layout_scanner', 'name' => 'scanner_layout', 'label' => 'Layout',
		'sub_fields' => array( array( 'key' => 'field_scanner_layout_text', 'label' => 'Layout text', 'name' => 'layout_text', 'type' => 'text' ) ) ) ),
);
acf_import_field_group( array(
	'key'          => 'group_scanner',
	'title'        => 'Scanner fields',
	'fields'       => $fields,
	'location'     => array( array( array( 'param' => 'post_type', 'operator' => '==', 'value' => 'post' ) ) ),
	'show_in_rest' => 1,
	'active'       => true,
) );
$post_id = wp_insert_post( array( 'post_title' => 'Scanner post', 'post_status' => 'publish', 'post_author' => 1 ) );
update_field( 'scanner_text', 'Scanner value', $post_id );
update_field( 'scanner_repeater', array( array( 'row_text' => 'Row one' ) ), $post_id );
PHP
cat > /usr/local/bin/scanner-runtime-check.php <<'PHP'
<?php
if ( ! class_exists( 'ACF' ) || ! acf_get_field_group( 'group_scanner' ) ) {
	throw new RuntimeException( 'The plugin or the seeded field group did not load.' );
}
$post = get_posts( array( 'title' => 'Scanner post', 'post_type' => 'post', 'numberposts' => 1 ) )[0];
wp_set_current_user( 0 );
$response = rest_do_request( new WP_REST_Request( 'GET', "/wp/v2/posts/{$post->ID}" ) );
if ( 200 !== $response->get_status() || 'Scanner value' !== ( $response->get_data()['acf']['scanner_text'] ?? null ) ) {
	throw new RuntimeException( 'Published post fields are not readable over REST.' );
}
foreach ( array( 0, get_user_by( 'login', 'subscriber' )->ID ) as $user_id ) {
	wp_set_current_user( $user_id );
	$request = new WP_REST_Request( 'POST', "/wp/v2/posts/{$post->ID}" );
	$request->set_body_params( array( 'acf' => array( 'scanner_text' => 'changed' ) ) );
	$status = rest_do_request( $request )->get_status();
	if ( ! in_array( $status, array( 401, 403 ), true ) ) {
		throw new RuntimeException( "Unprivileged field write was not denied: $status" );
	}
}
echo "SCF loaded; field values readable on a published post; anonymous/subscriber writes denied.\n";
PHP
cat > /usr/local/bin/scanner-test <<'TEST'
#!/bin/bash
set -euo pipefail
cd /src
wp-start
trap wp-stop EXIT
wp eval-file /usr/local/bin/scanner-runtime-check.php --path="$WP_ROOT" --user=admin
curl --fail --silent --show-error http://127.0.0.1/scanner-post/ >/dev/null
vendor/bin/phpunit --fail-on-empty-test-suite
npm run test:unit -- --ci
TEST
chmod +x /usr/local/bin/scanner-test
wp-start
wp eval-file /usr/local/bin/scanner-seed.php --path="$WP_ROOT" --user=admin
wp plugin list --path="$WP_ROOT" --status=active --fields=name,version
wp-stop
SH
