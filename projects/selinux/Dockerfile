FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential pkg-config git python3 \
	bison \
	flex \
	gawk \
	gcc \
	gettext \
	libaudit-dev \
	libbz2-dev \
	libcap-dev \
	libcap-ng-dev \
	libcunit1-dev \
	libdbus-glib-1-dev \
	libpcre2-dev \
	libpam0g-dev \
	libpam-modules \
	ruby-dev \
	swig \
	xmlto \
	python3-build \
	python3-dev \
	python3-pip \
	python3-setuptools \
	python3-wheel \
	&& rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN make -k DEBUG=1 LSPP_PRIV=y DESTDIR=/src/build install install-pywrap

# Smoke-test
RUN make -k DESTDIR=/src/build -C libsepol test
