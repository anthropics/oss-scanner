
FROM php:8.5-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git unzip curl ca-certificates \
    libicu-dev libxml2-dev libxslt1-dev \
    libpng-dev libjpeg62-turbo-dev libfreetype6-dev \
    libzip-dev libpq-dev libmagickwand-dev \
    libonig-dev libsqlite3-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) \
       gd intl xsl zip pdo_sqlite pdo_pgsql \
       sockets pcntl gettext calendar \
    && pecl install redis imagick \
    && docker-php-ext-enable redis imagick \
    && rm -rf /var/lib/apt/lists/*

RUN echo "memory_limit=1G" > /usr/local/etc/php/conf.d/memory-limit.ini

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# Anthropic erwartet den Quellcode in /src
COPY . /src
WORKDIR /src

# Projektabhängigkeiten einschließlich Testwerkzeugen installieren
RUN composer install --no-interaction --prefer-dist --no-progress

CMD ["/bin/bash"]
