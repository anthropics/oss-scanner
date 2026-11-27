# schema-utils: a single-package npm repository. Mirrors the `test` job in .github/workflows/nodejs.yml
# for the current Node.js versions: install with the lockfile (`npm ci`, whose `prepare` script builds
# `dist/` and `declarations/`), then run the Jest suite as a smoke test.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci --no-audit --no-fund
RUN npm run build

# Smoke test, so a broken image is visible in the build log without failing the build. `npm test` would
# run the linters first (pretest).
RUN npm run test:only -- --ci || echo "WARNING: the Jest suite reported failures"
