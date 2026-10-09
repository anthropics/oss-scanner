# Builds the php_clickhouse extension (with TLS) against Debian trixie's PHP 8.4 (CI's Linux matrix covers 7.4-8.6).
# Most phpts need a ClickHouse server, so the image carries the same pinned clickhouse-server that CI runs as a
# service container, listening on loopback only (127.0.0.1, plus 127.0.0.2 for the TLS hostname-mismatch test): plaintext native 9000 and TLS native 9440 with a CA generated
# here. Start it with `clickhouse-test-server` before running the suite; nothing needs the network afterwards.
FROM clickhouse/clickhouse-server@sha256:fdc22372465a336fa47e9deab61fad8277b9e2f2473234a1294b33b53f01d377 AS clickhouse

FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang autoconf pkg-config git python3 curl openssl libssl-dev \
      locales php8.4-cli php8.4-dev \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^# *de_DE.UTF-8 UTF-8/de_DE.UTF-8 UTF-8/' /etc/locale.gen && locale-gen

COPY --from=clickhouse /usr/bin/clickhouse /usr/bin/clickhouse
COPY --from=clickhouse /etc/clickhouse-server /etc/clickhouse-server
RUN set -e; \
    for tool in server client local; do ln -sf /usr/bin/clickhouse "/usr/bin/clickhouse-$tool"; done; \
    rm -f /etc/clickhouse-server/config.d/docker_related_config.xml; \
    mkdir -p /var/lib/clickhouse /var/log/clickhouse-server /etc/clickhouse-server/certs; \
    printf '%s\n' '<clickhouse>' '  <listen_host>127.0.0.1</listen_host>' '  <listen_host>127.0.0.2</listen_host>' '  <listen_try>1</listen_try>' \
      '</clickhouse>' > /etc/clickhouse-server/config.d/listen.xml; \
    printf '%s\n' '<clickhouse><users><test>' '  <password>test</password>' \
      '  <networks><ip>::/0</ip></networks>' '  <profile>default</profile><quota>default</quota>' \
      '  <access_management>1</access_management>' '</test></users></clickhouse>' \
      > /etc/clickhouse-server/users.d/test.xml; \
    cd /etc/clickhouse-server/certs; \
    openssl req -x509 -nodes -newkey rsa:2048 -keyout server.key -out server.crt -days 3650 \
      -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"; \
    openssl req -x509 -nodes -newkey rsa:2048 -keyout wrong.key -out wrong.crt -days 3650 -subj "/CN=wrong-ca"; \
    chmod 644 ./*.key ./*.crt; \
    printf '%s\n' '#!/bin/sh' \
      '# Starts the local ClickHouse test server in the background and waits for the native port.' \
      'if php -r "exit(@fsockopen(\"127.0.0.1\", 9000, \$e, \$s, 1) ? 0 : 1);"; then exit 0; fi' \
      'clickhouse server --config-file=/etc/clickhouse-server/config.xml --daemon --pid-file=/var/run/clickhouse-server.pid || exit 1' \
      'i=0; while [ $i -lt 60 ]; do' \
      '  php -r "exit(@fsockopen(\"127.0.0.1\", 9000, \$e, \$s, 1) ? 0 : 1);" && exit 0' \
      '  i=$((i+1)); sleep 1' \
      'done' \
      'echo "clickhouse-test-server: native port 9000 not reachable; see /var/log/clickhouse-server/" >&2; exit 1' \
      > /usr/local/bin/clickhouse-test-server; \
    chmod 755 /usr/local/bin/clickhouse-test-server

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
RUN cp /src/tests/tls/tls.xml /etc/clickhouse-server/config.d/tls.xml

RUN phpize \
    && ./configure --enable-clickhouse --enable-clickhouse-openssl \
         CFLAGS="-g -O2 -fno-omit-frame-pointer" CXXFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=clickhouse -r 'exit(class_exists("ClickHouse") ? 0 : 1);'

# The phpts declare --EXTENSIONS-- clickhouse, which resolves through the installed copy in extension_dir.
# -j1: the phpts share ClickHouse tables.
ENV CLICKHOUSE_HOST=127.0.0.1 \
    CLICKHOUSE_PORT=9000 \
    CLICKHOUSE_TLS_PORT=9440 \
    CLICKHOUSE_USER=test \
    CLICKHOUSE_PASSWD=test \
    CLICKHOUSE_TLS_SKIP_VERIFY=0 \
    CLICKHOUSE_TLS_CA_FILE=/etc/clickhouse-server/certs/server.crt \
    CLICKHOUSE_TLS_WRONG_CA_FILE=/etc/clickhouse-server/certs/wrong.crt \
    TEST_PHP_EXECUTABLE=/usr/bin/php \
    NO_INTERACTION=1
RUN cd /src && { clickhouse-test-server || echo "WARNING: ClickHouse test server did not start; server phpts will skip"; }; \
    (php run-tests.php -q -j1 --show-diff -g FAIL,BORK,LEAK,XLEAK tests/ \
      || echo "WARNING: phpt suite reported failures"); \
    kill "$(cat /var/run/clickhouse-server.pid 2>/dev/null)" 2>/dev/null; sleep 5; true
