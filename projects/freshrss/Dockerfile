# Note: This image does not start the Apache server automatically.
# It must be started manually in the shell using `apachectl start`.

FROM debian:trixie

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_MAJOR=22
ARG PLAYWRIGHT_VERSION=1.64.1

ENV TZ=UTC \
    FRESHRSS_ENV=development \
    COPY_LOG_TO_SYSLOG=On \
    COPY_SYSLOG_TO_STDERR=On \
    CRON_MIN='' \
    DATA_PATH='' \
    ENABLE_ACCESS_LOG=1 \
    TRUSTED_PROXY=0 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    NODE_PATH=/usr/lib/node_modules \
    PATH="/src/bin:${PATH}"

# Base utilities.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    gnupg \
    bash \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22.
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -

# Application runtime, databases and development tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    libapache2-mod-php \
    php-cli \
    php-curl \
    php-gmp \
    php-intl \
    php-mbstring \
    php-xml \
    php-zip \
    php-sqlite3 \
    php-mysql \
    php-pgsql \
    php-opcache \
    php-bcmath \
    php-gd \
    php-bz2 \
    php-ldap \
    php-readline \
    php-soap \
    php-xsl \
    \
    sqlite3 \
    postgresql \
    postgresql-client \
    mariadb-server \
    mariadb-client \
    \
    nodejs \
    \
    git \
    gpg \
    make \
    gcc \
    g++ \
    build-essential \
    pkg-config \
    golang-go \
    python3 \
    \
    gdb \
    strace \
    ltrace \
    valgrind \
    procps \
    psmisc \
    lsof \
    \
    openssl \
    socat \
    netcat-openbsd \
    tcpdump \
    iproute2 \
    iputils-ping \
    dnsutils \
    apache2-utils \
    \
    acl \
    attr \
    file \
    \
    libxml2-utils \
    jq \
    \
    ripgrep \
    fd-find \
    sed \
    gawk \
    grep \
    findutils \
    diffutils \
    patch \
    tree \
    less \
    vim-tiny \
    unzip \
    zip \
    xz-utils \
    \
    shellcheck \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Configure timezone and PHP settings.
RUN ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && find /etc/php*/ -type f -name php.ini -exec sed -i -E \
        -e "\#^;?date.timezone#s#^.*#date.timezone = $TZ#" \
        -e "\#^;?post_max_size#s#^.*#post_max_size = 32M#" \
        -e "\#^;?session.upload_progress.enabled#s#^.*#session.upload_progress.enabled = Off#" \
        -e "\#^;?upload_max_filesize#s#^.*#upload_max_filesize = 32M#" {} \;

# Convenient fd command name on Debian.
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd

# Install Node.js Playwright and Chromium.
RUN npm install --global "playwright@${PLAYWRIGHT_VERSION}" \
    && playwright install --with-deps chromium \
    && chmod -R a+rX /opt/ms-playwright \
    && rm -rf /var/lib/apt/lists/*

# Copy the complete FreshRSS repository.
WORKDIR /src
COPY --chown=root:www-data . /src

# Set up FreshRSS Apache configuration.
RUN mkdir -p /var/www /run/apache2 \
    && ln -s /src /var/www/FreshRSS \
    && cp /src/Docker/*.Apache.conf /etc/apache2/sites-available/

# Configure Apache.
RUN a2dismod -q -f alias autoindex negotiation status \
    && a2disconf -q '*' \
    && a2dissite -q '*' \
    && sed -r -i \
        '/^\s*(CustomLog|ErrorLog|Listen) /s/^/#/' \
        /etc/apache2/apache2.conf \
    && sed -r -i \
        '/^\s*Listen /s/^/#/' \
        /etc/apache2/ports.conf \
    && sed -i 's/^Listen 80$/Listen 8080/' \
        /etc/apache2/sites-available/FreshRSS.Apache.conf \
    && a2enmod -q deflate expires filter headers mime remoteip setenvif \
    && a2ensite -q 'FreshRSS*'

# Disable unnecessary PHP modules.
RUN phpdismod \
    calendar exif ffi ftp gettext mysqli posix readline \
    shmop sockets sysvmsg sysvsem sysvshm xsl

RUN apache2ctl configtest

# Disable built-in FreshRSS updates in this development image.
RUN sed -r -i \
    '\#disable_update#s#^.*#\t'\''disable_update'\'' => true,#' \
    /src/config.default.php

# Development user.
RUN useradd --create-home --groups www-data --shell /bin/bash developer \
    && install -d -m 0755 /etc/sudoers.d \
    && printf 'developer ALL=(ALL) NOPASSWD: ALL\n' \
        > /etc/sudoers.d/developer \
    && chmod 0440 /etc/sudoers.d/developer \
    && git config --system --add safe.directory /src

# Install shell development tools.
RUN mkdir -p /src/bin \
    && GOBIN=/src/bin go install \
        mvdan.cc/sh/v3/cmd/shfmt@v3.8.0 \
    && curl -fsSL \
        https://github.com/hadolint/hadolint/releases/download/v2.15.1/hadolint-linux-x86_64 \
        -o /src/bin/hadolint \
    && echo 'c7187db94eeeeca956519a6af171adc31453941a1e777961f6e680f697c8c507  /src/bin/hadolint' \
        | sha256sum -c - \
    && chmod 0755 /src/bin/shfmt /src/bin/hadolint

# Install JavaScript dependencies.
RUN npm ci

# Run FreshRSS's complete Makefile test suite.
RUN make test-all

RUN ./cli/access-permissions.sh
EXPOSE 8080
