FROM node:22-bookworm

ENV CXXFLAGS="-include cstddef"

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential cmake git python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN git submodule update --init --recursive \
    && npm ci \
    && npm run build \
    && (npm run test || echo "WARNING: npm run test reported failures")