FROM oven/bun:1.4.0

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN cd /src/core && bun install
RUN cd /src/standalone && bun install

RUN cd /src/core && bun link \
    && cd /src/standalone && bun link capjs-core

RUN cd /src/core && (bun test || echo "WARNING: core tests reported failures")
RUN redis-server --daemonize yes && sleep 1 \
    && cd /src/standalone && (bun test || echo "WARNING: standalone tests reported failures")
