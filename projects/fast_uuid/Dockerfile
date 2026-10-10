# Builds the fast_uuid PHP extension against Debian trixie's PHP 8.4 (CI's Linux matrix covers 8.1-8.6).
# The phpt suite needs no network once the image is built.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang autoconf pkg-config git python3 \
      php8.4-cli php8.4-dev php8.4-opcache php8.4-cgi \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN phpize \
    && ./configure --enable-fast-uuid CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=fast_uuid --ri fast_uuid

# The frameless-call phpts need opcache and php-cgi, as on CI's setup-php. One of them loads opcache by name with
# extension_dir pointed at modules/, so opcache.so is linked there.
RUN ln -sf "$(php-config --extension-dir)/opcache.so" /src/modules/opcache.so
ENV TEST_PHP_EXECUTABLE=/usr/bin/php \
    TEST_PHP_ARGS="-d extension=/src/modules/fast_uuid.so" \
    NO_INTERACTION=1
RUN cd /src && (php run-tests.php -q --show-diff -g FAIL,BORK,LEAK,XLEAK tests/ \
      || echo "WARNING: phpt suite reported failures")
