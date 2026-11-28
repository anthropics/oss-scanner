# php_excel: PHP extension wrapping the closed-source LibXL library. Mirrors the "linux" job in
# .github/workflows/tests.yml (PHP 8.4 lane, LibXL 5.2.0.1 ceiling) on Debian's PHP 8.4 packages.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    LIBXL_VERSION=5.2.0.1 \
    LIBXL_SHA256=447431d3046869428bf7182356bab1cfc04ef04e14eaf7118cc4193faadc53ae
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential autoconf pkg-config git python3 file \
      php8.4-cli php8.4-dev \
    && rm -rf /var/lib/apt/lists/*

# LibXL is proprietary and not redistributable; fetch the exact build CI pins from the vendor's public download
# URL and verify it. Without a license key LibXL runs in trial mode, which the PHPT suite is written for.
RUN mkdir -p /opt/dl && cd /opt/dl \
    && curl -fsSL "https://www.libxl.com/download/libxl-lin-${LIBXL_VERSION}.tar.gz" -o libxl.tar.gz \
    && echo "${LIBXL_SHA256}  libxl.tar.gz" | sha256sum -c - \
    && tar xzf libxl.tar.gz \
    && mv "$(find . -maxdepth 1 -type d -name 'libxl-*' | head -1)" /opt/libxl \
    && rm -rf /opt/dl /opt/libxl/php_excel /opt/libxl/examples /opt/libxl/lib /opt/libxl/lib-armhf \
    && test -f /opt/libxl/include_c/libxl.h \
    && echo /opt/libxl/lib64 > /etc/ld.so.conf.d/libxl.conf && ldconfig

COPY . /src
WORKDIR /src

RUN phpize \
    && CFLAGS="-g -O2 -fno-omit-frame-pointer" ./configure \
         --with-excel \
         --with-libxl-incdir=/opt/libxl/include_c \
         --with-libxl-libdir=/opt/libxl/lib64 \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=excel -r 'exit(extension_loaded("excel") ? 0 : 1);'

# Runs the PHPT suite against the built module: /usr/local/bin/run-phpt [run-tests.php args, default tests/]
RUN cat > /usr/local/bin/run-phpt <<'EOF' && chmod +x /usr/local/bin/run-phpt
#!/bin/sh
cd /src || exit 1
export LD_LIBRARY_PATH=/opt/libxl/lib64
export TEST_PHP_EXECUTABLE="$(command -v php)"
export TEST_PHP_ARGS="-d extension=/src/modules/excel.so"
export NO_INTERACTION=1
[ $# -eq 0 ] && set -- tests/
exec php run-tests.php -q --show-diff "$@"
EOF

RUN run-phpt || echo "WARNING: php_excel PHPT suite reported failures"
