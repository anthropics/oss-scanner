# Builds the pdo_duckdb PDO driver against Debian trixie's PHP 8.4 (CI's Linux matrix covers 8.1-8.6; Pdo\Duckdb
# needs 8.4+) and the prebuilt libduckdb release that CI pins. The phpt suite and PHP's shared ext/pdo/tests
# suite are fetched here and need no network once the image is built.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang autoconf pkg-config git python3 curl unzip \
      php8.4-cli php8.4-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# libduckdb version tracks DUCKDB_VERSION in .github/workflows/tests.yml; the checksum comes from the repository.
ARG DUCKDB_VERSION=1.5.5
RUN set -e; asset=libduckdb-linux-amd64.zip; \
    curl -fsSL -o "/tmp/$asset" "https://github.com/duckdb/duckdb/releases/download/v${DUCKDB_VERSION}/$asset"; \
    (cd /tmp && grep "  $asset\$" /src/.github/duckdb-sha256.txt | sha256sum --check --strict); \
    mkdir -p /tmp/duckdb /opt/duckdb/include /opt/duckdb/lib; \
    unzip -o "/tmp/$asset" -d /tmp/duckdb; \
    install -m644 /tmp/duckdb/duckdb.h /opt/duckdb/include/; \
    install -m755 /tmp/duckdb/libduckdb.so /opt/duckdb/lib/; \
    echo /opt/duckdb/lib > /etc/ld.so.conf.d/duckdb.conf; ldconfig; \
    rm -rf /tmp/duckdb "/tmp/$asset"

RUN phpize \
    && ./configure --with-pdo-duckdb=/opt/duckdb CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=pdo_duckdb -r 'exit((new PDO("duckdb::memory:"))->query("SELECT 42")->fetchColumn() === 42 ? 0 : 1);'

# PHP's generic PDO conformance tests at the installed release tag, for scripts/pdo-common-tests.sh.
RUN set -e; full="$(php -r 'echo PHP_VERSION;')"; \
    case "$full" in *[!0-9.]*) ref="PHP-$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')" ;; *) ref="php-$full" ;; esac; \
    git clone --depth=1 --branch="$ref" --filter=blob:none --sparse https://github.com/php/php-src.git /opt/php-src; \
    git -C /opt/php-src sparse-checkout set ext/pdo/tests

ENV TEST_PHP_EXECUTABLE=/usr/bin/php \
    TEST_PHP_ARGS="-d extension=/src/modules/pdo_duckdb.so" \
    NO_INTERACTION=1
RUN cd /src && (php run-tests.php -q --show-diff -g FAIL,BORK,LEAK,XLEAK tests/ \
      || echo "WARNING: phpt suite reported failures")
RUN cd /src && (env -u TEST_PHP_ARGS PHP=/usr/bin/php RUN_TESTS=/src/run-tests.php \
      COMMON_DIR=/opt/php-src/ext/pdo/tests DUCKDB_PREFIX=/opt/duckdb EXT=/src/modules/pdo_duckdb.so \
      bash scripts/pdo-common-tests.sh || echo "WARNING: PDO common suite reported failures")
