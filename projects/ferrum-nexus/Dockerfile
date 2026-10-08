FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git bash python3 build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src

# Build the shared workspace first through the root build script. Keep dev dependencies.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npm rebuild esbuild \
    && npm run build \
    && npm --prefix e2e ci --ignore-scripts --no-audit --no-fund \
    && npm --prefix e2e rebuild esbuild \
    && npm --prefix e2e exec --no -- playwright install --with-deps chromium

CMD ["bash"]
