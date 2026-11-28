# webpack-dev-middleware: a single-package npm repository (package-lock.json v3). Mirrors the `test` and
# `client` jobs in .github/workflows/nodejs.yml: `npm ci`, which also builds dist/, client/ and types/
# through the `prepare` script, then the Jest suites, with the browser suites (test/e2e) driving the
# Chrome that puppeteer downloads.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    PUPPETEER_CACHE_DIR=/opt/puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci

RUN apt-get update && npx puppeteer browsers install chrome --install-deps \
    && rm -rf /var/lib/apt/lists/*
RUN test -f dist/index.js && test -f client/index.js || npm run build

# Smoke test, so a broken image is visible in the build log without failing the build. `npm test` would
# run the linters first (pretest); the other suites are listed in threat_model.md.
RUN npm run test:only -- --ci test/validation-options.test.js test/utils \
    || echo "WARNING: the smoke test reported failures"
