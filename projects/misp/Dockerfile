# syntax=docker/dockerfile:1
# Match MISP's Ubuntu 24.04 / PHP 8.3 CI environment. The scanner supplies
# MISP/MISP as the build context; fetch dependencies now for the offline audit.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/src/venv/bin:$PATH

RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && apt-get update && apt-get install -y --no-install-recommends \
      apache2 libapache2-mod-php8.3 mariadb-server mariadb-client redis-server \
      php8.3-cli php8.3-mysql php8.3-mbstring php8.3-xml php8.3-curl \
      php8.3-zip php8.3-intl php8.3-bcmath php8.3-gd php8.3-redis \
      php8.3-gnupg php8.3-apcu composer \
      python3 python3-dev python3-venv build-essential libfuzzy-dev libmagic1 \
      ca-certificates curl git gnupg unzip sudo \
    && rm -rf /var/lib/apt/lists/*

COPY --exclude=.oss-scanner/Dockerfile . /src
WORKDIR /src

# Optional trust anchor for development environments with an HTTPS inspection
# proxy. Leave unset for normal builds; TLS verification remains enabled.
ARG EXTRA_CA_CERT
RUN if [ -n "$EXTRA_CA_CERT" ]; then \
      printf '%s\n' "$EXTRA_CA_CERT" > /usr/local/share/ca-certificates/extra-ca.crt \
      && update-ca-certificates; \
    fi

# tools/check clones without submodules. Populate the exact recorded revisions,
# including CakePHP, PyMISP, the STIX helpers and MISP's bundled data sets.
RUN git submodule update --init --recursive --depth 1 --jobs 4
RUN composer --working-dir=app install --no-interaction --no-progress --prefer-dist
RUN python3 -m venv /src/venv \
    && python -m pip install -r requirements.txt -r requirements-dev.txt

# Use the repository's CI configuration and database fixtures. These are local
# test credentials, never an instance intended to serve production traffic.
RUN <<'SH'
set -eu
cp app/Config/bootstrap.default.php app/Config/bootstrap.php
cp app/Config/core.default.php app/Config/core.php
cp app/Config/config.default.php app/Config/config.php
cp build/database.php app/Config/database.php
cp build/email.php app/Config/email.php
cp build/github-action-ci-apache /etc/apache2/sites-available/misp.conf
sed -i 's|%GITHUB_WORKSPACE%|/src|g; s|%HOST%|localhost|g' /etc/apache2/sites-available/misp.conf
printf 'ServerName localhost\n' > /etc/apache2/conf-available/servername.conf
a2enconf servername
a2dissite 000-default
a2ensite misp
a2enmod rewrite
for sapi in cli apache2; do
    printf 'memory_limit = 512M\nopcache.revalidate_freq = 0\n' > "/etc/php/8.3/$sapi/conf.d/99-misp.ini"
done
mkdir -p app/tmp/logs app/tmp/cache/models app/tmp/cache/persistent app/files/scripts/tmp
chmod -R a+rX /src
chown -R www-data:www-data app/Config app/tmp app/files
service mariadb start
redis-server --daemonize yes
mariadb -e "CREATE DATABASE misp; CREATE USER 'misp'@'127.0.0.1' IDENTIFIED BY 'blah'; GRANT ALL PRIVILEGES ON misp.* TO 'misp'@'127.0.0.1'; SET GLOBAL sql_mode = 'STRICT_ALL_TABLES';"
mariadb misp < INSTALL/MYSQL.sql
install -d -o www-data -g www-data -m 700 /src/.gnupg
sudo -u www-data gpg --batch --pinentry-mode loopback --passphrase '' \
    --homedir /src/.gnupg --quick-generate-key \
    'MISP scanner test <info@admin.test>' rsa2048 sign 0
sudo -u www-data app/Console/cake Admin setSetting MISP.python_bin /src/venv/bin/python
sudo -u www-data app/Console/cake Admin setSetting MISP.baseurl http://localhost
sudo -u www-data app/Console/cake Admin setSetting --force MISP.disable_emailing true
sudo -u www-data app/Console/cake Admin setSetting --force MISP.background_jobs false
sudo -u www-data app/Console/cake Admin setSetting SimpleBackgroundJobs.enabled true
sudo -u www-data app/Console/cake Admin setSetting GnuPG.email info@admin.test
sudo -u www-data app/Console/cake Admin setSetting GnuPG.homedir /src/.gnupg
sudo -u www-data app/Console/cake Admin runUpdates
# Keep generated test-instance authentication material private inside the image.
sudo -u www-data app/Console/cake User init > /root/misp-test-admin.txt
chmod 600 /root/misp-test-admin.txt
service mariadb stop
redis-cli shutdown

# Services do not survive the build or the transition to the offline shell.
# This helper starts only services inside this image and checks the login page.
cat > /usr/local/bin/misp-start <<'START'
#!/bin/bash
set -euo pipefail
service mariadb start
redis-cli ping > /dev/null 2>&1 || redis-server --daemonize yes
apache2ctl start
mariadb-admin ping --silent
test "$(redis-cli ping)" = PONG
page=$(mktemp)
trap 'rm -f "$page"' EXIT
curl --fail --silent --show-error http://localhost/users/login --output "$page"
grep -q 'id="UserEmail"' "$page"
echo 'MISP services ready on the container loopback interface.'
START
chmod 755 /usr/local/bin/misp-start

# Run the offline-capable PHP and STIX regression suites.
sudo -u www-data app/Vendor/bin/phpunit --do-not-cache-result app/Test/
python -m pytest -q tests/test_misp_framing.py tests/test_stix2misp_wrapper.py
SH

CMD ["bash"]
