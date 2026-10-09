# Uppy: Yarn 4 (corepack) monorepo. Mirrors .github/workflows/ci.yml.
FROM node:24-bookworm
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    YARN_ENABLE_GLOBAL_CACHE=false \
    CI=true

RUN corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN corepack yarn install --immutable
# Browser tests (Vitest browser mode) need Chromium, which must be fetched while the network is up.
RUN corepack yarn workspace @uppy/dashboard playwright install --with-deps chromium
RUN corepack yarn run build

# Smoke-test the image; failures are logged, not fatal. Full suite: `corepack yarn test`.
RUN corepack yarn workspace @uppy/companion test || echo "WARNING: companion tests reported failures"
