FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang gdb git patch pkg-config \
      python3 python3-venv xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/r2pipe \
    && /opt/r2pipe/bin/pip install --no-cache-dir r2pipe
ENV PATH="/opt/r2pipe/bin:${PATH}"

COPY . /src
WORKDIR /src

# Build fetches the pinned subprojects; keep them available for offline rebuilds.
RUN CFLAGS="-O1 -g -fno-omit-frame-pointer" \
      ./configure --prefix=/usr/local --without-syscapstone \
    && make -j2 \
    && make install \
    && ldconfig

# Fetch the regression corpus while networking is still available.
RUN make -C test bins
RUN r2 -v && rabin2 -v && r2r -v
