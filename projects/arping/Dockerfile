FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang cmake ninja-build pkg-config git \
      python3 libnet1-dev libpcap-dev libseccomp-dev libcap-dev autoconf \
      automake check iproute2 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN ./bootstrap.sh && ./configure && make check
