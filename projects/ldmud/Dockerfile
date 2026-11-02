FROM debian:trixie

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential ca-certificates bison autoconf autogen automake \
                                               pkg-config locales python3-dev zlib1g-dev \
                                               libgcrypt20-dev libgnutls28-dev libc-ares-dev libpcre2-dev \
                                               libsqlite3-dev libpq-dev libmariadb-dev \
                                               libxml2-dev libjson-c-dev

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && dpkg-reconfigure --frontend=noninteractive locales && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/src

RUN ./autogen.sh
RUN ./configure --enable-use-ipv6 --enable-use-mccp --enable-use-json --enable-use-pcre --enable-use-mysql \
                --enable-use-pgsql --enable-use-sqlite --enable-use-xml --enable-use-tls  --enable-use-gcrypt \
                --enable-malloc-trace --enable-malloc-lpc-trace  --enable-dynamic-costs --enable-eval-cost-trace \
                --enable-trace-code --enable-swap-efun --enable-use-python

RUN make

ENV DRIVER="../src/ldmud --hostname localhost --hostaddr 0.0.0.0"
RUN cd ../test && ./run.sh
