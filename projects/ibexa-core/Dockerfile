# Ibexa DXP Open Source: the ibexa/core package.
#
# /src           the ibexa/core git checkout (the repository named in project.yaml, on its default branch: the latest
#                development version), with its own dev dependencies so its unit and SQLite integration tests run
#                offline (`composer unit`, `composer integration`).
# /opt/ibexa     an Ibexa DXP Open Source site on the same development version, installed with Ibexa's manual
#                procedure for development branches (the same one Ibexa's CI uses): `composer create-project
#                ibexa/website-skeleton`, `composer require ibexa/oss`, the Flex recipes, `post-update-cmd`, then
#                `bin/console ibexa:install`. ibexa/core is installed from /src as a symlinked path repository, so the
#                site runs the checkout and a patch to /src takes effect on the site straight away.
#
# Nothing here names a version. The version to install (for example 6.0.x-dev) is read from the checkout's branch
# alias, so the build follows the repository's default branch to the next version on its own. Only the PHP base
# image below may need raising when a new version requires a newer PHP.
#
# The site runs in the prod environment, served by Apache with the front controller in /opt/ibexa/public, on MariaDB.
# Start both with `ibexa-start`; the site listens on http://127.0.0.1/ and the back office on http://127.0.0.1/admin.
#
# To scan another Ibexa package (ibexa/admin-ui, ibexa/rest, ...), change IBEXA_PACKAGE below and `repo:` in
# project.yaml; the rest of this file stays the same.
FROM php:8.5-apache-trixie

ARG IBEXA_PACKAGE=ibexa/core

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1 \
    COMPOSER_MEMORY_LIMIT=-1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip curl procps jq mariadb-server mariadb-client \
      libfreetype6-dev libjpeg62-turbo-dev libpng-dev libwebp-dev libzip-dev libicu-dev libxslt1-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
    && docker-php-ext-install -j"$(nproc)" gd zip intl xsl bcmath exif pdo_mysql \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Node.js and Yarn build the back office assets (`composer run post-install-cmd` runs Webpack Encore).
COPY --from=node:22-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g yarn@1 \
    && node --version && yarn --version

# Production-like PHP, per Ibexa's security checklist: errors are logged, not shown, and stack traces leave out
# arguments; OPcache picks up edited files immediately so a patch can be
# checked straight away. The console and the test suites get more memory than a web request.
RUN { echo 'memory_limit=512M'; \
      echo 'error_reporting=E_ALL'; \
      echo 'display_errors=Off'; \
      echo 'display_startup_errors=Off'; \
      echo 'zend.exception_ignore_args=On'; \
      echo 'log_errors=On'; \
      echo 'error_log=/dev/stderr'; \
      echo 'opcache.validate_timestamps=1'; \
      echo 'opcache.revalidate_freq=0'; \
    } > /usr/local/etc/php/conf.d/oss-scanner.ini

# Apache serves /opt/ibexa/public with the rewrite rules of Ibexa's official virtual host template
# (ibexa/post-install, resources/templates/apache2/vhost.template), filled in for this image and with mod_php in place
# of PHP-FPM. Only image storage and built assets are served directly; everything else goes to the front controller.
COPY <<'APACHE' /etc/apache2/sites-available/000-default.conf
<VirtualHost *:80>
    ServerName 127.0.0.1
    DocumentRoot /opt/ibexa/public
    DirectoryIndex index.php
    LimitRequestBody 0
    TimeOut 90

    <Directory /opt/ibexa/public>
        Options FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    SetEnvIf Request_URI ".*" APP_ENV=prod
    SetEnv APP_DEBUG "0"

    <IfModule mod_rewrite.c>
        RewriteEngine On
        RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
        RewriteRule ^var/.*(?i)\.(php3?|phar|phtml|sh|exe|pl|bin)$ - [F]
        RewriteCond %{ENV:BINARY_DATA_HANDLER} "dfs"
        RewriteRule ^/var/([^/]+/)?storage/images(-versioned)?/.* /index.php [L]
        RewriteRule ^/var/([^/]+/)?storage/images(-versioned)?/.* - [L]
        RewriteRule ^/favicon\.ico - [L]
        RewriteRule ^/robots\.txt - [L]
        RewriteRule ^/bundles/ - [L]
        RewriteRule ^/assets/ - [L]
        RewriteRule ^/build/ - [L]
        RewriteCond %{ENV:APP_ENV} !^(dev)
        RewriteRule ^/(css|js|fonts?)/.*\.(css|js|otf|eot|ttf|svg|woff) - [L]
        RewriteRule ^/([^/]+/)*?index\.php([/?#]|$) - [R=404,L]
        RewriteRule .* /index.php
    </IfModule>

    ErrorLog /dev/stderr
    CustomLog /dev/stdout combined
</VirtualHost>
APACHE
RUN a2enmod rewrite headers expires && echo 'ServerName 127.0.0.1' > /etc/apache2/conf-enabled/servername.conf

# ibexa-start starts MariaDB and Apache (there is no init system in the container). It is safe to run again.
# ibexa-console runs bin/console as www-data, the Apache user, so the cache and files it writes stay usable by the site.
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld' \
      'mariadb-admin ping --silent 2>/dev/null || (mysqld_safe >/dev/null 2>&1 &)' \
      'until mariadb-admin ping --silent 2>/dev/null; do sleep 0.5; done' \
      'pgrep -x apache2 >/dev/null || apachectl start' \
      > /usr/local/bin/ibexa-start \
    && printf '%s\n' '#!/bin/sh' 'apachectl stop 2>/dev/null; mariadb-admin shutdown 2>/dev/null; true' \
      > /usr/local/bin/ibexa-stop \
    && printf '%s\n' '#!/bin/sh' 'cd /opt/ibexa && exec su -s /bin/sh www-data -c "php bin/console $*"' \
      > /usr/local/bin/ibexa-console \
    && chmod +x /usr/local/bin/ibexa-start /usr/local/bin/ibexa-stop /usr/local/bin/ibexa-console

# scanner contract: the ibexa/core checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The development version of the checkout, from its branch alias (for example 6.0.x-dev), as Ibexa's CI reads it.
RUN jq -r '.extra["branch-alias"] | flatten | .[0]' /src/composer.json > /etc/ibexa-version \
    && grep -Eq '^[0-9]+\.[0-9]+\.x-dev$' /etc/ibexa-version \
    && echo "Ibexa version: $(cat /etc/ibexa-version)"

# The package's own dev dependencies (PHPUnit, ibexa/test-core), so its tests run offline.
RUN COMPOSER_ROOT_VERSION="$(cat /etc/ibexa-version)" composer install --no-progress

# Build the site with Ibexa's manual installation procedure for development branches. The skeleton points Symfony
# Flex at Ibexa's development recipes through the GitHub API, which allows 60 anonymous requests an hour; read the same
# index from raw.githubusercontent.com instead (the recipes themselves are already fetched from there).
RUN composer create-project --no-install --no-progress "ibexa/website-skeleton:$(cat /etc/ibexa-version)" /opt/ibexa
WORKDIR /opt/ibexa
RUN version="$(cat /etc/ibexa-version)" \
    && composer config extra.symfony.endpoint https://raw.githubusercontent.com/ibexa/recipes-dev/flex/main/index.json \
    && composer config repositories.src "{\"type\": \"path\", \"url\": \"/src\", \"options\": {\"symlink\": true, \"versions\": {\"${IBEXA_PACKAGE}\": \"${version}\"}}}" \
    && composer require --no-update "${IBEXA_PACKAGE}:${version}" \
    && composer require -W --no-scripts --no-progress "ibexa/oss:${version}" \
    && git config --global --add safe.directory /opt/ibexa \
    && git init -q && git add . && git -c user.name=oss-scanner -c user.email=oss-scanner@localhost commit -qm "Installed Ibexa DXP" \
    && composer recipes:install ibexa/oss --force --reset \
    && composer recipes:install "${IBEXA_PACKAGE}" --force --reset \
    && NODE_OPTIONS='--max-old-space-size=3072' composer run-script post-update-cmd

# The site's configuration: prod environment, MariaDB, the Legacy search engine (the default, no Solr). It goes in
# .env.local, not the image's environment, so it doesn't override the SQLite settings of the /src test suites.
RUN { echo 'APP_ENV=prod'; \
      echo 'APP_DEBUG=0'; \
      echo "APP_SECRET=$(php -r 'echo bin2hex(random_bytes(32));')"; \
      echo 'DATABASE_URL=mysql://ibexa:ibexa@127.0.0.1:3306/ibexa?serverVersion=11.8.0-MariaDB&charset=utf8mb4'; \
      echo 'SEARCH_ENGINE=legacy'; \
    } > .env.local

# Test users for access-control reproductions, created through the public PHP API by a small console command:
#   admin / publish          the installer's administrator (Administrator role)
#   editor / Editor1234!     in the Editors group (Editor role): back office access, content editing
#   member / Member1234!     in the Guest accounts group (Anonymous role): logged in on the front end, no back office
#   (anonymous)              no login
COPY <<'PHP' /opt/ibexa/src/Command/CreateTestUsersCommand.php
<?php

declare(strict_types=1);

namespace App\Command;

use Ibexa\Contracts\Core\Repository\PermissionResolver;
use Ibexa\Contracts\Core\Repository\UserService;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

#[AsCommand(name: 'oss-scanner:create-test-users', description: 'Creates the editor and member test users.')]
final class CreateTestUsersCommand extends Command
{
    private const USERS = [
        // login, password, user group content ID (13: Editors, 11: Guest accounts in the clean install)
        ['editor', 'Editor1234!', 13],
        ['member', 'Member1234!', 11],
    ];

    public function __construct(
        private readonly UserService $userService,
        private readonly PermissionResolver $permissionResolver,
    ) {
        parent::__construct();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $this->permissionResolver->setCurrentUserReference($this->userService->loadUserByLogin('admin'));
        foreach (self::USERS as [$login, $password, $groupId]) {
            $struct = $this->userService->newUserCreateStruct($login, $login . '@example.com', $password, 'eng-GB');
            $struct->setField('first_name', ucfirst($login));
            $struct->setField('last_name', 'Test');
            $this->userService->createUser($struct, [$this->userService->loadUserGroup($groupId)]);
            $output->writeln("Created {$login}");
        }

        return Command::SUCCESS;
    }
}
PHP

# Install the clean data, then create the test users. MariaDB is stopped again at the end of the step.
RUN ibexa-start \
    && mariadb -e "CREATE DATABASE ibexa CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci; \
         CREATE USER 'ibexa'@'%' IDENTIFIED BY 'ibexa'; GRANT ALL ON ibexa.* TO 'ibexa'@'%';" \
    && apachectl stop \
    && php bin/console ibexa:install --no-interaction \
    && php bin/console ibexa:graphql:generate-schema \
    && php bin/console cache:clear \
    && php bin/console oss-scanner:create-test-users \
    && chown -R www-data:www-data /opt/ibexa/var /opt/ibexa/public /opt/ibexa/config/graphql \
    && ibexa-stop

# Smoke-run the unit tests so the build log shows whether they pass. This deliberately doesn't fail the build:
# the default branch moves, and a red test on the day of a build shouldn't stop the scan.
WORKDIR /src
RUN (composer unit -- --no-progress || echo "WARNING: ibexa/core unit tests reported failures")
