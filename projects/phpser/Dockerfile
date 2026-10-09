# Builds the phpser PHP extension against Debian trixie's PHP 8.4 (CI's Linux matrix
# covers 8.4). The phpt suite needs no network once the image is built.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang autoconf pkg-config git python3 valgrind \
      php8.4-cli php8.4-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN phpize \
    && ./configure --enable-phpser CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make -j"$(nproc)" \
    && php -d extension=/src/modules/phpser.so -m | grep -qx phpser

ENV TEST_PHP_EXECUTABLE=/usr/bin/php \
    TEST_PHP_ARGS="-d extension=/src/modules/phpser.so" \
    NO_INTERACTION=1
RUN cd /src && (php run-tests.php -q --show-diff -g FAIL,BORK,LEAK,XLEAK tests/ \
      || echo "WARNING: phpt suite reported failures")
