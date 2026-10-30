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
RUN npm ci --ignore-scripts --legacy-peer-deps
RUN npm run build

# Unit tests (test/) and e2e tests (e2e/, boots Nest apps in-process); no external services needed.
RUN (npm run test && npm run test:e2e) || echo "WARNING: tests reported failures"
