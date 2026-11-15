FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CC=gcc \
    CXX=g++
# Dependencies from doc/README.compilation (Ubuntu/Debian section)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git bison flex libxml2-dev libpcap-dev libtool libtool-bin rrdtool librrd-dev \
      autoconf pkg-config automake autogen redis-server wget libsqlite3-dev libhiredis-dev libmaxminddb-dev \
      libcurl4-openssl-dev libpango1.0-dev libcairo2-dev libnetfilter-queue-dev zlib1g-dev libssl-dev libcap-dev \
      libnetfilter-conntrack-dev libreadline-dev libjson-c-dev libldap2-dev rename libsnmp-dev libexpat1-dev \
      libradcli-dev libzmq3-dev curl jq libnl-genl-3-dev libgcrypt20-dev cmake libzstd-dev libmariadb-dev-compat \
      python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# ntopng builds against the nDPI sources placed next to it (doc/README.compilation)
RUN git clone --depth 1 https://github.com/ntop/nDPI.git /nDPI \
    && cd /nDPI && ./autogen.sh && ./configure CFLAGS="-g -fno-omit-frame-pointer" && make -j"$(nproc)"

RUN ./autogen.sh \
    && ./configure CFLAGS="-g -fno-omit-frame-pointer" CXXFLAGS="-g -fno-omit-frame-pointer" \
    && make -j"$(nproc)"
