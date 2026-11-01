FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential python3 git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Frontend + relay dependencies (network is available only during this build)
RUN npm ci --no-audit --no-fund
RUN cd gun-relay-server && (npm ci --no-audit --no-fund || npm install --no-audit --no-fund) || true

# Production build of the Vue frontend
RUN npm run build

# Cheap tests; a failing test must not abort the build
RUN (npm test || echo "WARNING: vitest reported failures")
