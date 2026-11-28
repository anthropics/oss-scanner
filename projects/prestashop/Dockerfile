# PrestaShop core, built from the maintenance branch named in project.yaml the way the release archive is built:
# `composer install --no-dev` (which also installs the native modules and the Classic and Hummingbird themes listed
# in composer.json into modules/ and themes/), then the front and back office assets.
#
# /src           the PrestaShop checkout, built and installed. Apache serves /src, so a patch takes effect on the
#                next request. Files the build and the installer create are ignored by git, so `git diff` shows a
#                patch.
#
# Apache runs with mod_rewrite and AllowOverride All, so PrestaShop's .htaccess files apply as in production. The
# database is MariaDB. Start both with `ps-start`; the shop is at http://127.0.0.1/ and the back office at
# http://127.0.0.1/admin-dev/.
FROM php:8.4-apache-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_PROCESS_TIMEOUT=1200

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps mariadb-server mariadb-client \
    && rm -rf /var/lib/apt/lists/*
ADD --chmod=0755 https://github.com/mlocati/docker-php-extension-installer/releases/download/2.12.0/install-php-extensions /usr/local/bin/
RUN install-php-extensions bcmath gd intl pdo_mysql zip opcache
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node for the asset build (PrestaShop's docker-compose.yml uses Node 20).
COPY --from=node:20-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# Production-like PHP: errors are logged, not shown; OPcache picks up edited files immediately so a patch can be checked
# straight away.
RUN printf '%s\n' memory_limit=512M upload_max_filesize=64M post_max_size=64M max_input_vars=10000 \
      display_errors=Off log_errors=On error_log=/dev/stderr opcache.validate_timestamps=1 opcache.revalidate_freq=0 \
      > /usr/local/etc/php/conf.d/oss-scanner.ini

# Apache serves /src. A release has no installer, no git metadata and no development files; here they are in the
# docroot because it is a checkout, so keep them off the web.
RUN a2enmod rewrite headers expires \
    && sed -ri 's!/var/www/html!/src!g' /etc/apache2/sites-available/000-default.conf \
    && printf '%s\n' '<Directory /src>' '  AllowOverride All' '  Require all granted' '</Directory>' \
         'RedirectMatch 404 ^/(install-dev|tests|tools|docs|\.[^/]+)(/|$)' 'RedirectMatch 404 /node_modules/' \
         'ServerName 127.0.0.1' > /etc/apache2/conf-available/prestashop.conf \
    && a2enconf prestashop

# ps-start starts MariaDB and Apache (there is no init system in the container) and is safe to run again.
# ps-console runs bin/console as www-data, the user Apache runs as.
RUN printf '%s\n' '#!/bin/sh' 'set -e' 'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' > /usr/local/bin/ps-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' > /usr/local/bin/ps-stop \
    && printf '%s\n' '#!/bin/sh' 'cd /src && exec setpriv --reuid=www-data --regid=www-data --init-groups php bin/console "$@"' \
      > /usr/local/bin/ps-console \
    && chmod +x /usr/local/bin/ps-start /usr/local/bin/ps-stop /usr/local/bin/ps-console \
    && git config --system --add safe.directory /src

# scanner contract: the checkout lives inside the image, at /src. It belongs to www-data, the user Apache runs as,
# and the build runs as that user too, so the shop can write where it needs to.
COPY --chown=www-data:www-data . /src
WORKDIR /src

RUN setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp sh -c \
      'composer install --no-dev --optimize-autoloader --no-progress && ./tools/assets/build.sh all --force'

# Seed restricted accounts for access-control reproductions: one employee per default non-SuperAdmin profile and two
# customers. Passwords follow the pattern OssScanner-<login>1!.
COPY <<'EOF' /usr/local/share/prestashop/seed-accounts.php
<?php
require '/src/config/config.inc.php';

$crypto = PrestaShop\PrestaShop\Adapter\ServiceLocator::get(PrestaShop\PrestaShop\Core\Crypto\Hashing::class);
$langId = (int) Configuration::get('PS_LANG_DEFAULT');
$profiles = array_column(Profile::getProfiles($langId), 'id_profile', 'name');

foreach (['Logistician' => 'AdminOrders', 'Translator' => 'AdminTranslations', 'Salesman' => 'AdminOrders'] as $profile => $landingTab) {
    $login = strtolower($profile);
    $employee = new Employee();
    $employee->firstname = $profile;
    $employee->lastname = 'Employee';
    $employee->email = "$login@example.com";
    $employee->passwd = $crypto->hash("OssScanner-{$login}1!");
    $employee->id_profile = (int) $profiles[$profile];
    $employee->id_lang = $langId;
    $employee->default_tab = (int) Tab::getIdFromClassName($landingTab);
    $employee->active = true;
    $employee->add() or exit("could not add employee $login\n");
    $employee->associateTo(Shop::getShops(false, null, true));
}

foreach (['alice', 'bob'] as $login) {
    $customer = new Customer();
    $customer->firstname = ucfirst($login);
    $customer->lastname = 'Customer';
    $customer->email = "$login@example.com";
    $customer->passwd = $crypto->hash("OssScanner-{$login}1!");
    $customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
    $customer->active = true;
    $customer->add() or exit("could not add customer $login\n");
    $customer->updateGroup([$customer->id_default_group]);
}
EOF

# Install the shop with the demo catalog, with _PS_MODE_DEV_ off as on a live shop (config/defines_custom.inc.php is
# ignored by git). Accounts:
#   admin@example.com / OssScanner-admin1!   SuperAdmin
#   logistician@, translator@, salesman@example.com, alice@ and bob@example.com (see above)
#   pub@prestashop.com / 123456789           demo customer with an address and orders
RUN printf '%s\n' '<?php' "define('_PS_MODE_DEV_', false);" > config/defines_custom.inc.php \
    && chown www-data:www-data /src config/defines_custom.inc.php \
    && ps-start \
    && mariadb -e "CREATE DATABASE prestashop; CREATE USER 'prestashop'@'%' IDENTIFIED BY 'prestashop'; \
         GRANT ALL ON prestashop.* TO 'prestashop'@'%';" \
    && setpriv --reuid=www-data --regid=www-data --init-groups php install-dev/index_cli.php \
         --domain=127.0.0.1 --db_server=127.0.0.1 --db_name=prestashop --db_user=prestashop --db_password=prestashop \
         --prefix=ps_ --name="OSS Scanner PrestaShop" --country=us --language=en \
         --firstname=Admin --lastname=Scanner --email=admin@example.com --password='OssScanner-admin1!' \
         --newsletter=0 --send_email=0 --ssl=0 --rewrite=1 --fixtures=1 \
    && setpriv --reuid=www-data --regid=www-data --init-groups php /usr/local/share/prestashop/seed-accounts.php \
    && ps-console prestashop:config set PS_MAIL_METHOD --value 3 \
    && rm -rf var/cache/* \
    && curl -fsS -o /dev/null http://127.0.0.1/ \
    && curl -fsS -o /dev/null http://127.0.0.1/admin-dev/login \
    && ps-stop \
    && printf '.oss-scanner/\n' >> .git/info/exclude
