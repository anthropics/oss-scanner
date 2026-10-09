FROM node:24-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git openssl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/capture-venv \
    && /opt/capture-venv/bin/pip install --no-cache-dir mitmproxy
ENV PATH="/opt/capture-venv/bin:${PATH}"

# The scanner supplies a fresh public checkout, including Git metadata.
COPY . /src
WORKDIR /src
RUN npm ci --no-audit --no-fund \
    && npm --prefix site ci --no-audit --no-fund \
    && npm run build
