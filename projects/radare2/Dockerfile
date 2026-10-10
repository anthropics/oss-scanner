FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang libclang-rt-dev gdb git patch pkg-config \
      python3 python3-venv xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/r2pipe \
    && /opt/r2pipe/bin/pip install --no-cache-dir r2pipe
ENV PATH="/opt/r2pipe/bin:${PATH}"

COPY . /src
WORKDIR /src

# Select build jobs using radare2's CPU/RAM detection; keep the scanned revision.
# The default symlink installation also picks up subsequent offline rebuilds.
RUN CFLAGS="-O1 -g -fno-omit-frame-pointer" \
      sys/install.sh --without-pull --prefix=/usr/local \
    && ldconfig

# Fetch the regression corpus while networking is still available.
RUN make -C test bins
RUN r2 -v && rabin2 -v && r2r -v

ENV R2R_OFFLINE=1
