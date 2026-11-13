# syntax=docker/dockerfile:1
# Matomo Analytics.
#
# /src           the Matomo git checkout (the repository named in project.yaml), with its plugin submodules checked out,
#                its Composer dependencies (including dev dependencies for PHPUnit) installed, and a working Matomo
#                installed into it, the way the web installer at https://matomo.org/faq/on-premise/installing-matomo/
#                does it
#
# The site is served by Apache with AllowOverride All, so Matomo's generated .htaccess protections apply as they do in
# production. The database is MariaDB, and Redis is there for the QueuedTracking plugin. Start all three with
# `matomo-start`; the site listens on http://127.0.0.1/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1

# git-lfs because the checkout's git hooks may call it; Matomo's .lfsconfig keeps it from downloading the UI screenshots.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git git-lfs unzip curl procps mariadb-server mariadb-client redis-server \
    && rm -rf /var/lib/apt/lists/*

# The base image already provides OPcache, curl, mbstring, xml and zlib. These are the rest of the extensions Matomo's
# own CI installs (https://github.com/matomo-org/github-action-tests); ldap and redis are for the LoginLdap and
# QueuedTracking plugins.
ADD --chmod=0755 https://github.com/mlocati/docker-php-extension-installer/releases/download/2.12.0/install-php-extensions /usr/local/bin/
RUN install-php-extensions gd zip bcmath pdo_mysql mysqli ldap redis
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Production-like PHP: errors are logged (to Apache's error log), not shown; OPcache picks up edited files immediately so
# a patch can be checked straight away. local_infile lets archiving use LOAD DATA LOCAL INFILE, as Matomo's CI does.
RUN { echo 'memory_limit=768M'; \
      echo 'max_execution_time=0'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'log_errors=On'; \
      echo 'mysqli.allow_local_infile=On'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

# Apache serves /src with .htaccess enabled. mod_php does not put a Bearer `Authorization` header into $_SERVER, so pass
# it through as HTTP_AUTHORIZATION, as Matomo's CI (nginx + php-fpm) and most PHP-FPM setups do, so API requests can
# authenticate with `Authorization: Bearer <token_auth>`. The base image links Apache's logs to the console, which a
# daemonised Apache does not have; make them real files, so PHP and Apache errors end up in
# /var/log/apache2/error.log.
RUN a2enmod rewrite headers expires \
    && sed -ri 's!/var/www/html!/src!g' /etc/apache2/sites-available/000-default.conf \
    && printf '<Directory /src>\n  Options -MultiViews +FollowSymLinks\n  AllowOverride All\n  Require all granted\n</Directory>\nServerName 127.0.0.1\nSetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1\n' \
         > /etc/apache2/conf-available/matomo.conf \
    && a2enconf matomo \
    && rm -f /var/log/apache2/*.log

# There is no mail server. This sendmail writes each email Matomo sends (invitations, password resets, scheduled
# reports, alerts) to /var/mail/matomo/, so reproductions can read the links in them.
RUN mkdir -p /var/mail/matomo && chown www-data:www-data /var/mail/matomo \
    && printf '%s\n' '#!/bin/sh' 'cat > "/var/mail/matomo/$(date +%Y%m%d-%H%M%S)-$$.eml"' > /usr/sbin/sendmail \
    && chmod +x /usr/sbin/sendmail

# Helpers (there is no init system in the container):
#   matomo-start     hands tmp/, config/ and js/ back to www-data (files that root creates there, for example by running
#                    ./console directly, would stop the site from writing its caches and Tag Manager containers), then
#                    starts MariaDB, Redis and Apache. Safe to run again: apachectl itself checks whether Apache is
#                    running (without an init system, a stopped Apache leaves zombie processes that pgrep would find).
#   matomo-stop      stops all three.
#   as-www-data      runs a command as www-data, the user Apache runs as and the owner of /src.
#   matomo-console   ./console as www-data.
#   matomo-phpunit   PHPUnit as www-data, with Matomo's phpunit.xml.dist.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'chown -R www-data:www-data /src/tmp /src/config /src/js' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes >/dev/null' \
      'apachectl start' \
      > /usr/local/bin/matomo-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; redis-cli shutdown nosave 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/matomo-stop \
    && printf '%s\n' '#!/bin/sh' 'exec setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp COMPOSER_HOME=/tmp/composer "$@"' \
      > /usr/local/bin/as-www-data \
    && printf '%s\n' '#!/bin/sh' 'cd /src && exec as-www-data php /src/console "$@"' > /usr/local/bin/matomo-console \
    && printf '%s\n' '#!/bin/sh' 'cd /src && exec as-www-data /src/vendor/bin/phpunit -c /src/tests/PHPUnit/phpunit.xml.dist "$@"' \
      > /usr/local/bin/matomo-phpunit \
    && chmod +x /usr/local/bin/matomo-start /usr/local/bin/matomo-stop /usr/local/bin/as-www-data \
         /usr/local/bin/matomo-console /usr/local/bin/matomo-phpunit \
    && git config --system --add safe.directory '*'

# scanner contract: the Matomo checkout lives inside the image, at /src. Like a production install, the web server owns
# the Matomo directory, so it can write config/, tmp/ and the Tag Manager containers in js/. The scanner works as root,
# so git is told to trust the directory (above).
COPY --chown=www-data:www-data . /src
WORKDIR /src

# The scanner clones without submodules. Check them out at the commits the checkout pins, as Matomo's own setup does
# (`git submodule update --init`), so the bundled plugins (TagManager, CustomAlerts, QueuedTracking, LoginLdap, ...)
# are present. Then the PHP dependencies, including the dev ones (PHPUnit), as Matomo's CI installs them.
RUN as-www-data git submodule update --init --depth 1 \
    && git submodule status \
    && as-www-data composer install --no-progress \
    && rm -rf /tmp/composer /tmp/.cache

# Install Matomo by driving the web installer, as an administrator would in a browser, then seed what access-control
# reproductions need through the HTTP API: a second website, one user per role, and an app token per user, written to
# /root/matomo-tokens.txt. Each password is "<login>-password".
#   admin        super user
#   siteadmin    admin access to idsite 1
#   writer       write access to idsite 1
#   viewer       view access to idsite 1
#   viewer2      view access to idsite 2 only
#   (anonymous)  view access to idsite 2 only, so the anonymous surfaces (widgets, public reports) can be reached
# Databases: `matomo` for the site, `matomo_tests` for PHPUnit, which drops and recreates it.
RUN <<'EOF'
#!/bin/bash
set -euo pipefail
matomo-start
mariadb -e "CREATE DATABASE matomo; CREATE DATABASE matomo_tests;
            CREATE USER 'matomo'@'%' IDENTIFIED BY 'matomo'; GRANT ALL ON *.* TO 'matomo'@'%';"

url=http://127.0.0.1/index.php
jar=$(mktemp)
step() { curl -fsS -b "$jar" -c "$jar" -o /dev/null -w "$1: %{http_code}\n" "$url?module=Installation&action=$1" "${@:2}"; }
step databaseSetup --data-urlencode host=127.0.0.1 --data-urlencode username=matomo --data-urlencode password=matomo \
  --data-urlencode dbname=matomo --data-urlencode tables_prefix=matomo_ --data-urlencode adapter=PDO\\MYSQL \
  --data-urlencode schema=Mariadb
step tablesCreation
step setupSuperUser --data-urlencode login=admin --data-urlencode password=admin-password \
  --data-urlencode password_bis=admin-password --data-urlencode email=admin@example.com
step firstWebsiteSetup --data-urlencode siteName="Example site" --data-urlencode url=http://example.com \
  --data-urlencode timezone=UTC --data-urlencode ecommerce=1
step finished --data-urlencode anonymise_ip=1
rm -f "$jar"
if grep -q installation_in_progress config/config.ini.php; then echo "the installer did not finish" >&2; exit 1; fi
[[ "$(curl -fsS "$url")" == *module=Login* ]] || { echo "the installed site does not show the login" >&2; exit 1; }

# The API answers errors with HTTP 200 and {"result":"error"}, so check the body.
api() {
  curl -fsS "$url?module=API&format=json&method=$1" "${@:2}" | php -r '
    $r = json_decode(stream_get_contents(STDIN), true);
    if (!is_array($r) || ($r["result"] ?? "") === "error") { fwrite(STDERR, ($r["message"] ?? "bad response") . "\n"); exit(1); }
    echo $r["value"] ?? "";'
}
# A user creates their own app token, as the "Personal > Security" page does.
token() {
  api UsersManager.createAppSpecificTokenAuth --data-urlencode "userLogin=$1" \
    --data-urlencode "passwordConfirmation=$1-password" --data-urlencode description=oss-scanner
}
admin=$(token admin)
echo "admin $admin" > /root/matomo-tokens.txt
api SitesManager.addSite -d "token_auth=$admin" --data-urlencode siteName="Second site" \
  --data-urlencode urls=http://second.example.com
for spec in siteadmin:admin:1 writer:write:1 viewer:view:1 viewer2:view:2; do
  IFS=: read -r login access idsite <<< "$spec"
  api UsersManager.addUser -d "token_auth=$admin" -d "userLogin=$login" -d "password=$login-password" \
    -d "email=$login@example.com"
  api UsersManager.setUserAccess -d "token_auth=$admin" -d "userLogin=$login" -d "access=$access" -d "idSites=$idsite"
  user_token=$(token "$login")
  echo "$login $user_token" >> /root/matomo-tokens.txt
done
api UsersManager.setUserAccess -d "token_auth=$admin" -d userLogin=anonymous -d access=view -d idSites=2
cat /root/matomo-tokens.txt
matomo-stop
EOF

# Activate the submodule plugins that work offline and leave the core flows alone, and run their database updates
# (Matomo refuses requests until they have run). Left inactive: LoginLdap (replaces
# the login), QueuedTracking (moves tracking onto a Redis queue), Provider (reverse DNS for every visit),
# DeviceDetectorCache and AnonymousPiwikUsageMeasurement (reports usage to matomo.org).
# Then track a few days of visits through the real tracker (matomo.php) with the VisitorGenerator development plugin
# and archive them, so reports, Live and segments have data. Finally point PHPUnit's test database settings at
# matomo_tests and its HTTP requests at this Apache.
RUN <<'EOF'
#!/bin/bash
set -euo pipefail
matomo-start
matomo-console plugin:activate TagManager CustomAlerts MarketingCampaignsReporting CustomVariables \
  TreemapVisualization TasksTimetable LogViewer Bandwidth SecurityInfo VisitorGenerator
matomo-console core:update --yes
matomo-console visitorgenerator:generate-visits --idsite=1 --days=3 --limit-fake-visits=200 \
  --custom-matomo-url=http://127.0.0.1/
matomo-console visitorgenerator:generate-visits --idsite=2 --days=1 --limit-fake-visits=50 --no-logs \
  --custom-matomo-url=http://127.0.0.1/
matomo-console plugin:deactivate VisitorGenerator
matomo-console core:archive --url=http://127.0.0.1/
matomo-console config:set 'database_tests.username="matomo"' 'database_tests.password="matomo"' \
  'tests.http_host="127.0.0.1"' 'tests.request_uri="/"'
matomo-stop
EOF

# Smoke-test the site, the API and the test setup, without letting a failing test abort the build.
RUN <<'EOF'
#!/bin/bash
set -euo pipefail
matomo-start
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/config/config.ini.php)" = 403
curl -fsS -H "Authorization: Bearer $(awk '$1 == "viewer" { print $2 }' /root/matomo-tokens.txt)" \
  "http://127.0.0.1/index.php?module=API&method=SitesManager.getSitesIdWithAtLeastViewAccess&format=json"
echo
matomo-phpunit --testsuite UnitTests --filter 'Piwik\\Tests\\Unit\\UrlHelperTest' \
  || echo "WARNING: unit tests reported failures"
matomo-phpunit tests/PHPUnit/Integration/AccessTest.php --filter testAPIWithAuthorizationHeader \
  || echo "WARNING: integration test reported failures"
matomo-phpunit tests/PHPUnit/System/TrackerResponseTest.php || echo "WARNING: system test reported failures"
matomo-stop
# Start the scan with an empty error log and mailbox: what is in them now came from the build, not from a reproduction.
: > /var/log/apache2/error.log
rm -f /var/mail/matomo/*.eml
EOF

# Keep build products out of the checkout's `git status`.
RUN printf '.oss-scanner/\n' >> /src/.git/info/exclude && git status --short
