FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git bash python3 build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src

# Retain development dependencies and fetch the supported browser while online.
RUN npm ci --no-audit --no-fund \
    && npm exec --no -- playwright install --with-deps chromium \
    && npm run build

CMD ["bash"]
