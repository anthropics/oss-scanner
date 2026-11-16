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
	selinux-policy-dev \
	&& rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build and install everything.
RUN make -k DEBUG=1 LSPP_PRIV=y DESTDIR=/src/build install install-pywrap

# Run tests as an unprivileged user, matching upstream CI: several test
# expectations assert DAC mode-bit semantics that do not hold for uid 0.
RUN useradd -m scanner && chown -R scanner:scanner /src
USER scanner

# Run the tests once
RUN DESTDIR=/src/build ./scripts/env_use_destdir make -k test
