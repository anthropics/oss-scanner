# SPDX-License-Identifier: MPL-2.0
#
# Base NaviServer installation
#
FROM debian:trixie-slim

RUN DEBIAN_FRONTEND=noninteractive apt-get -qq update  && DEBIAN_FRONTEND=noninteractive apt-get install -y adduser locales  && sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen  && dpkg-reconfigure --frontend=noninteractive locales  && update-locale LANG=en_US.UTF-8

ENV LC_ALL=en_US.UTF-8

# Defaults allow the scanner to build without Makefile build arguments.
# ".." builds the supplied checkout, the parent of .scanner-install-ns.
ARG version_ns=..
ARG version_modules=GIT
ARG version_tcl=8.6.18
ARG version_tcllib=1.20
ARG version_xotcl=2.5.0
ARG version_openssl=4.0.3

ENV PATH="/usr/local/ns/openssl-${version_openssl}/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/ns/openssl-${version_openssl}/lib64:/usr/local/ns/openssl-${version_openssl}/lib"

ARG with_ns_doc=0
ARG with_system_malloc=1
ARG with_debug_flags=1
ARG version_tdom=0.9.6
ARG ns_modules="nsudp nssmtpd nsstats revproxy nsauthpam nsdns nsdbsqlite"
ARG system_pkgs=""

RUN addgroup --system nsadmin \
    && adduser --disabled-password --no-create-home --ingroup nsadmin --gecos "NaviServer Admin" nsadmin \
    && mkdir -p /scripts

# Scanner contract: retain the supplied checkout at /src.
COPY . /src
WORKDIR /src

RUN  DEBIAN_FRONTEND=noninteractive apt-get -qq update  && DEBIAN_FRONTEND=noninteractive apt-get -qq upgrade -y  && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y --no-install-recommends bash tzdata locales ca-certificates libtcmalloc-minimal4 $system_pkgs  && dev_packages="git patch curl libpam0g-dev wget build-essential autoconf automake pkg-config python3 vim-tiny gdb strace procps"  && DEBIAN_FRONTEND=noninteractive apt-get -qq install -y --no-install-recommends $dev_packages \
    && git clone https://github.com/gustafn/install-ns.git /src/.scanner-install-ns \
    && cd /src/.scanner-install-ns \
    && with_postgres=0 \
       version_ns="${version_ns}" \
       version_modules="${version_modules}" \
       version_tcl="${version_tcl}" \
       with_ns_doc=${with_ns_doc} \
       with_system_malloc=${with_system_malloc} \
       with_debug_flags=${with_debug_flags} \
       version_tcllib=${version_tcllib} \
       version_xotcl=${version_xotcl} \
       version_openssl=${version_openssl} \
       version_tdom=${version_tdom} \
       ns_modules=${ns_modules} \
       bash install-ns.sh build

# Keep dependency sources, build artifacts, headers, and development tools
# available for offline reproductions and rebuilding proposed fixes.
WORKDIR /src
