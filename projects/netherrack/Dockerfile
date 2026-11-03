# Netherrack is a Nextcloud app (nc_netherrack/ in the repository). The image installs Nextcloud with SQLite,
# builds the app's frontend, installs its PHP dev dependencies and enables it, so it can be exercised via occ,
# HTTP (apache on port 80) and PHPUnit.
FROM nextcloud:33-apache
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_NO_INTERACTION=1
RUN apt-get update && apt-get install -y --no-install-recommends git unzip curl ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && printf '%s\n' '#!/bin/sh' 'exec setpriv --reuid=www-data --regid=www-data --init-groups env HOME=/tmp "$@"' > /usr/local/bin/as-www-data \
    && printf '%s\n' '#!/bin/sh' 'exec as-www-data php /var/www/html/occ "$@"' > /usr/local/bin/occ \
    && chmod +x /usr/local/bin/as-www-data /usr/local/bin/occ \
    && git config --system --add safe.directory '*' \
    && rsync -a --chown=www-data:www-data /usr/src/nextcloud/ /var/www/html/ \
    && install -d -o www-data -g www-data /var/www/data

# scanner contract: the checkout lives inside the image, at /src
COPY --chown=www-data:www-data . /src
WORKDIR /src/nc_netherrack

RUN as-www-data composer install \
    && as-www-data npm ci --no-audit --no-fund \
    && as-www-data npm run build

# Nextcloud with SQLite; the app is linked into custom_apps and enabled. Users alice and bob for sharing tests.
RUN ln -s /src/nc_netherrack /var/www/html/custom_apps/nc_netherrack \
    && occ maintenance:install --database=sqlite --data-dir=/var/www/data --admin-user=admin --admin-pass=admin \
    && occ config:system:set apps_paths 0 path --value=/var/www/html/apps \
    && occ config:system:set apps_paths 0 url --value=/apps \
    && occ config:system:set apps_paths 0 writable --type=boolean --value=false \
    && occ config:system:set apps_paths 1 path --value=/var/www/html/custom_apps \
    && occ config:system:set apps_paths 1 url --value=/custom_apps \
    && occ config:system:set apps_paths 1 writable --type=boolean --value=true \
    && occ config:system:set appstoreenabled --type=boolean --value=false \
    && occ config:system:set trusted_domains 1 --value=localhost \
    && occ app:enable nc_netherrack \
    && occ app:disable password_policy \
    && OC_PASS=alice occ user:add --password-from-env alice \
    && OC_PASS=bob occ user:add --password-from-env bob \
    && occ netherrack:index:rebuild

RUN (as-www-data vendor/bin/phpunit || echo "WARNING: phpunit reported failures") \
    && (as-www-data npm run test:unit || echo "WARNING: vitest reported failures") \
    && apachectl start && sleep 2 \
    && (occ status --exit-code || echo "WARNING: occ status reported a problem") \
    && curl -s -o /dev/null -w 'login page: %{http_code}\n' http://localhost/login \
    && apachectl stop
