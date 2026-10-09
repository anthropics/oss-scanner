# fastchart: PHP chart/symbol rendering extension. Mirrors the "linux" (PHP 8.4, gcc) and "pdf" (--with-pdfio)
# jobs in .github/workflows/tests.yml on Debian's PHP 8.4 packages, so the PDF backend is built and scannable too.
# --enable-fastchart-dev is left off: it only adds -Werror/-Wstrict-prototypes, and a new compiler warning should
# not fail the scanner build.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    PDFIO_VERSION=1.6.4 \
    PDFIO_SHA256=1b5e5e945f4fc214b55d575554c1aec11d7ba91b397cef92ffe877462155af06
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential autoconf pkg-config git python3 file strace locales \
      php8.4-cli php8.4-dev php8.4-gd php8.4-xml \
      libfreetype-dev libpng-dev libjpeg62-turbo-dev libwebp-dev zlib1g-dev \
      fonts-lato fonts-dejavu-core \
    && sed -i 's/^# *\(de_DE.UTF-8 UTF-8\)/\1/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# pdfio (static) for renderPdf(), pinned to the version CI's pdf job uses.
RUN mkdir -p /opt/dl && cd /opt/dl \
    && curl -fsSL "https://github.com/michaelrsweet/pdfio/releases/download/v${PDFIO_VERSION}/pdfio-${PDFIO_VERSION}.tar.gz" -o pdfio.tar.gz \
    && echo "${PDFIO_SHA256}  pdfio.tar.gz" | sha256sum -c - \
    && mkdir src && tar xzf pdfio.tar.gz -C src --strip-components=1 \
    && cd src && CFLAGS="-g -O2 -fno-omit-frame-pointer -fPIC" ./configure --prefix=/opt/pdfio --disable-shared --enable-static \
    && make -j"$(nproc)" libpdfio.a && make install \
    && rm -rf /opt/dl

COPY . /src
WORKDIR /src

RUN phpize \
    && PKG_CONFIG_PATH=/opt/pdfio/lib/pkgconfig CFLAGS="-g -O2 -fno-omit-frame-pointer" ./configure \
         --enable-fastchart --with-pdfio=/opt/pdfio \
    && make -j"$(nproc)" \
    && make install \
    && php -d extension=fastchart --ri fastchart

# Runs the PHPT suite against the built module: /usr/local/bin/run-phpt [run-tests.php args, default tests/]
RUN cat > /usr/local/bin/run-phpt <<'EOF' && chmod +x /usr/local/bin/run-phpt
#!/bin/sh
cd /src || exit 1
export TEST_PHP_EXECUTABLE="$(command -v php)"
export TEST_PHP_ARGS="-d extension=/src/modules/fastchart.so"
export NO_INTERACTION=1
[ $# -eq 0 ] && set -- tests/
exec php run-tests.php -q --show-diff "$@"
EOF

RUN run-phpt || echo "WARNING: fastchart PHPT suite reported failures"
