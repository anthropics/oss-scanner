# webpack-sources: a single-package npm repository with no build step. Mirrors the Node.js 22+ `test` job
# in .github/workflows/test.yml: `npm ci`, then the `node --test` suite as a smoke test.
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

# Smoke test, so a broken image is visible in the build log without failing the build. `npm test` would
# run the linters first (pretest).
RUN node --require ./test/helpers/validate-mappings.js --test --test-reporter=dot "test/*.js" \
    || echo "WARNING: the node:test suite reported failures"
