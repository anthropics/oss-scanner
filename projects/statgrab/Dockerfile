# statgrab: PHP bindings for libstatgrab. Uses the bundled build from the "asan-bundled" job in
# .github/workflows/tests.yml so the patched vendored libstatgrab (vendor/libstatgrab) is compiled with debug info and
# statically linked into the module, on Debian's PHP 8.4 packages (CI covers 8.0 to 8.6).
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential autoconf automake libtool pkg-config git python3 file \
      php8.4-cli php8.4-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN cd vendor/libstatgrab \
    && autoreconf -fiv \
    && CFLAGS="-g -O2 -fno-omit-frame-pointer" ./configure --enable-static --disable-shared --without-ncurses --with-pic \
    && make -j"$(nproc)"

RUN phpize \
    && CFLAGS="-g -O2 -fno-omit-frame-pointer" ./configure --with-statgrab=bundled \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=statgrab --ri statgrab

# Runs the PHPT suite against the built module: /usr/local/bin/run-phpt [run-tests.php args, default tests/]
RUN cat > /usr/local/bin/run-phpt <<'EOF' && chmod +x /usr/local/bin/run-phpt
#!/bin/sh
cd /src || exit 1
export TEST_PHP_EXECUTABLE="$(command -v php)"
export TEST_PHP_ARGS="-d extension=/src/modules/statgrab.so"
export NO_INTERACTION=1
[ $# -eq 0 ] && set -- tests/
exec php run-tests.php -q --show-diff "$@"
EOF

RUN run-phpt || echo "WARNING: statgrab PHPT suite reported failures"
