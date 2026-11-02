# Akismet Anti-spam (akismet), scanned as a plugin inside a working WordPress site.
#
# /src                        the akismet-plugin-wordpress checkout (the repository named in project.yaml). It is the
#                             plugin as released: plain PHP, CSS and JS, with no build step, Composer or npm
#                             dependencies, or test suite
# /var/www/html               the WordPress install Apache serves, with /src symlinked in as wp-content/plugins/akismet
#                             (replacing the copy of Akismet that ships with WordPress)
# /var/www/html/wp-content/mu-plugins/oss-scanner-akismet-mock.php
#                             an offline stand-in for the Akismet API (rest.akismet.com); see threat_model.md
#
# Start MariaDB and Apache with `wp-start`; the site then listens on http://127.0.0.1/.
FROM php:8.3-apache-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    WP_CLI_ALLOW_ROOT=1 \
    WP_ROOT=/var/www/html

# mysqli is what WordPress uses; the rest are the extensions the WordPress hosting handbook recommends.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" mysqli pdo_mysql gd zip intl exif bcmath \
    && rm -rf /var/lib/apt/lists/*

# WP-CLI, for setting up content, users and options in reproductions.
RUN curl -fsSL -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x /usr/local/bin/wp \
    && wp --info

# Production-like PHP: errors are logged to /var/log/php-error.log, not shown; OPcache picks up edited files
# immediately so a patch can be checked straight away.
RUN { echo 'memory_limit=256M'; \
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

# Apache serves /var/www/html with .htaccess enabled (Akismet ships its own .htaccess that blocks direct access to
# its PHP files, so AllowOverride All matters here).
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

# scanner contract: the akismet checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Akismet has no build step. Lint every PHP file so a broken checkout fails the build.
RUN find /src -name '*.php' -not -path '*/.git/*' -print0 | xargs -0 -n1 php -l >/dev/null \
    && test -f /src/akismet.php

# Install a working single-site WordPress on MariaDB, with one user per default role for access-control reproductions:
#   admin / admin               administrator (fully trusted; has manage_options and moderate_comments)
#   editor / editor             editor        (moderates comments, no manage_options)
#   author / author             author
#   contributor / contributor   contributor
#   subscriber / subscriber     subscriber    (self-registerable; registration is enabled below)
#   (anonymous)                 no login; can comment on the sample post
# Akismet is active with the placeholder API key `0123456789ab`; the mock below accepts that key as valid.
RUN wp-start \
    && mariadb -e "CREATE DATABASE wordpress; \
         CREATE USER 'wordpress'@'%' IDENTIFIED BY 'wordpress'; \
         GRANT ALL ON wordpress.* TO 'wordpress'@'%';" \
    && rm -rf "$WP_ROOT"/* \
    && wp core download --path="$WP_ROOT" \
    && wp config create --path="$WP_ROOT" --dbname=wordpress --dbuser=wordpress --dbpass=wordpress \
         --dbhost=127.0.0.1 --skip-check \
    && wp core install --path="$WP_ROOT" --url=http://127.0.0.1 --title="OSS Scanner Akismet" \
         --admin_user=admin --admin_password=admin --admin_email=admin@example.com --skip-email \
    && for role in editor author contributor subscriber; do \
         wp user create --path="$WP_ROOT" "$role" "$role@example.com" --role="$role" --user_pass="$role"; \
       done \
    && rm -rf "$WP_ROOT/wp-content/plugins/akismet" \
    && ln -s /src "$WP_ROOT/wp-content/plugins/akismet" \
    && wp plugin activate akismet --path="$WP_ROOT" \
    && wp option update --path="$WP_ROOT" wordpress_api_key 0123456789ab \
    && wp option update --path="$WP_ROOT" users_can_register 1 \
    && wp option update --path="$WP_ROOT" comment_moderation 0 \
    && wp option update --path="$WP_ROOT" comment_previously_approved 0 \
    && wp option update --path="$WP_ROOT" akismet_comment_form_privacy_notice display \
    && wp rewrite structure --path="$WP_ROOT" '/%postname%/' \
    && printf '%s\n' '# BEGIN WordPress' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' \
         'RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]' 'RewriteRule ^index\.php$ - [L]' \
         'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' \
         '</IfModule>' '# END WordPress' > "$WP_ROOT/.htaccess" \
    && mkdir -p "$WP_ROOT/wp-content/uploads" \
    && chown -R www-data:www-data "$WP_ROOT/wp-content/uploads" \
    && wp plugin list --path="$WP_ROOT" --status=active --fields=name,version \
    && wp-stop

# Offline stand-in for the Akismet API. There is no network during the scan, so every call to rest.akismet.com would
# otherwise fail and Akismet would only ever take its "server unreachable" paths. This must-use plugin answers those
# calls locally, like the real service does for its documented test values:
#   verify-key               "valid" for the configured key, "invalid" otherwise
#   comment-check            "true" (spam) when the author is "akismet-guaranteed-spam" or the content contains
#                            "akismet-guaranteed-spam"; "false" (ham) otherwise; always with an X-akismet-guid
#   submit-spam, submit-ham  the usual thank-you body
#   anything else            falls through to the (absent) network, so it fails
# `wp option update oss_scanner_akismet_mock off` turns it off; the last request it saw is in the option
# oss_scanner_akismet_mock_last.
RUN mkdir -p "$WP_ROOT/wp-content/mu-plugins" \
    && printf '%s\n' \
      '<?php' \
      '// OSS Scanner: offline mock of the Akismet API. Not part of Akismet.' \
      'add_filter( "pre_http_request", function ( $pre, $args, $url ) {' \
      '	if ( "off" === get_option( "oss_scanner_akismet_mock" ) || "rest.akismet.com" !== wp_parse_url( $url, PHP_URL_HOST ) ) {' \
      '		return $pre;' \
      '	}' \
      '	$path = basename( (string) wp_parse_url( $url, PHP_URL_PATH ) );' \
      '	parse_str( is_string( $args["body"] ) ? $args["body"] : http_build_query( (array) $args["body"] ), $req );' \
      '	update_option( "oss_scanner_akismet_mock_last", array( "path" => $path, "request" => $req ), false );' \
      '	$headers = array();' \
      '	switch ( $path ) {' \
      '		case "verify-key":' \
      '			$body = ( isset( $req["key"] ) && $req["key"] === get_option( "wordpress_api_key" ) ) ? "valid" : "invalid";' \
      '			break;' \
      '		case "comment-check":' \
      '			$author  = isset( $req["comment_author"] ) ? $req["comment_author"] : "";' \
      '			$content = isset( $req["comment_content"] ) ? $req["comment_content"] : "";' \
      '			$body    = ( "akismet-guaranteed-spam" === $author || false !== strpos( $content, "akismet-guaranteed-spam" ) ) ? "true" : "false";' \
      '			$headers["x-akismet-guid"] = md5( wp_generate_uuid4() );' \
      '			break;' \
      '		case "submit-spam":' \
      '		case "submit-ham":' \
      '			$body = "Thanks for making the web a better place.";' \
      '			break;' \
      '		default:' \
      '			return $pre;' \
      '	}' \
      '	$headers = new WpOrg\Requests\Utility\CaseInsensitiveDictionary( $headers );' \
      '	return array( "headers" => $headers, "body" => $body, "response" => array( "code" => 200, "message" => "OK" ), "cookies" => array(), "filename" => null );' \
      '}, 10, 3 );' \
      > "$WP_ROOT/wp-content/mu-plugins/oss-scanner-akismet-mock.php" \
    && php -l "$WP_ROOT/wp-content/mu-plugins/oss-scanner-akismet-mock.php"

# Smoke test: check the key, then submit one ham and one spam comment through the real comment form, so you know the
# plugin is wired up. Do not let a failure abort the build.
RUN wp-start \
    && post_id="$(wp post list --path="$WP_ROOT" --post_type=post --field=ID --posts_per_page=1)" \
    && ( wp eval --path="$WP_ROOT" 'echo "verify-key: ", Akismet::verify_key( Akismet::get_api_key() ), "\n";' \
         && curl -fsS -o /dev/null -X POST http://127.0.0.1/wp-comments-post.php \
              --data-urlencode "comment_post_ID=$post_id" --data-urlencode 'author=Ham Tester' \
              --data-urlencode 'email=ham@example.com' --data-urlencode 'comment=A perfectly normal comment.' \
         && sleep 16 \
         && curl -fsS -o /dev/null -X POST http://127.0.0.1/wp-comments-post.php \
              --data-urlencode "comment_post_ID=$post_id" --data-urlencode 'author=akismet-guaranteed-spam' \
              --data-urlencode 'email=spam@example.com' --data-urlencode 'comment=Buy now.' \
         ; wp comment list --path="$WP_ROOT" --status=approve --fields=comment_ID,comment_author,comment_approved \
         && wp comment list --path="$WP_ROOT" --status=spam --fields=comment_ID,comment_author,comment_approved \
         || echo "WARNING: Akismet smoke test reported failures" ) \
    && wp-stop
