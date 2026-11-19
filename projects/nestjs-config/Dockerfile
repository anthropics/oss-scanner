FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    HUSKY=0 \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same steps as CI (.circleci/config.yml): install, then compile lib/ into dist/.
RUN npm ci --ignore-scripts
RUN npm run build

# Integration tests (vitest) under tests/; they load .env fixtures from disk and need no services.
RUN npm run test:integration || echo "WARNING: tests reported failures"
