FROM php:8.5-cli-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    APP_URL=http://127.0.0.1:8000 \
    DATABASE_URL=mysql://root:root@127.0.0.1:3306/shopware \
    LOCK_DSN=flock \
    SHOPWARE_ES_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg git unzip \
    && rm -rf /var/lib/apt/lists/*

# MariaDB 12.3 from the upstream MariaDB repository
RUN curl -fsSL https://mariadb.org/mariadb_release_signing_key.pgp \
      | gpg --dearmor -o /usr/share/keyrings/mariadb.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/mariadb.gpg] https://deb.mariadb.org/12.3/debian trixie main" \
      > /etc/apt/sources.list.d/mariadb.list \
    && apt-get update && apt-get install -y --no-install-recommends mariadb-server mariadb-client \
    && rm -rf /var/lib/apt/lists/*

# PHP extensions required by composer.json (the rest ship with the base image)
ADD --chmod=0755 https://github.com/mlocati/docker-php-extension-installer/releases/download/2.12.0/install-php-extensions /usr/local/bin/
RUN install-php-extensions gd intl pdo_mysql zip opcache redis pcntl exif \
    && printf 'memory_limit=-1\n' > /usr/local/etc/php/conf.d/zz-shopware.ini
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Starts MariaDB in the background (the scanner runs offline, so the database is local)
RUN printf '%s\n' '#!/bin/sh' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadbd-safe --user=mysql >/dev/null 2>&1 &' \
      'for i in $(seq 60); do mariadb-admin ping --silent && exit 0; sleep 1; done; exit 1' \
      > /usr/local/bin/start-mariadb && chmod +x /usr/local/bin/start-mariadb

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN composer install --no-interaction

# Install Shopware and the PHPUnit test database (shopware_test). The database files stay in the image,
# so `start-mariadb` is all that is needed before running bin/console or integration tests.
RUN start-mariadb \
    && mariadb -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'root'; FLUSH PRIVILEGES;" \
    && printf 'APP_ENV=dev\nAPP_SECRET=%s\nAPP_URL=%s\nDATABASE_URL=%s\nLOCK_DSN=flock\n' "$(php -r 'echo bin2hex(random_bytes(32));')" "$APP_URL" "$DATABASE_URL" > .env \
    && bin/console system:install --create-database --basic-setup --force --skip-assets-install \
    && composer init:testdb \
    && mariadb-admin -uroot -proot shutdown
