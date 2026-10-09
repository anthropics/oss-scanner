# Pure-PHP composer library. CI tests PHP 8.4 with dom, mbstring, xml and xmlwriter (all compiled into the
# official PHP CLI image). Dev dependencies and the aiosmtpd fixture used by the e2e group are installed here
# because the scan runs offline; the e2e tests talk only to a local aiosmtpd server on 127.0.0.1.
FROM php:8.4-cli-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git unzip python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# The e2e tests start tests/fixtures/smtp_test_server.py as plain `python3`, which a login shell resolves to
# /usr/bin/python3 regardless of ENV PATH, so aiosmtpd goes into the system interpreter's site-packages.
RUN pip install --break-system-packages --no-cache-dir aiosmtpd==1.4.6 \
    && /usr/bin/python3 -c 'import aiosmtpd' \
    && php -m | grep -qx dom && php -m | grep -qx mbstring && php -m | grep -qx xmlwriter

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN composer install --no-interaction --no-progress --prefer-dist \
    && composer dump-autoload --optimize

# Non-fatal smoke runs: unit tests (default suite) and the local-SMTP e2e group. Neither needs the network.
RUN vendor/bin/phpunit || echo "WARNING: phpunit (unit) reported failures"
RUN timeout 300 vendor/bin/phpunit --group e2e || echo "WARNING: phpunit (e2e) reported failures"
