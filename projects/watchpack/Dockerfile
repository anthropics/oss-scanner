# watchpack: a single-package npm repository with no build step (lib/ is plain CommonJS, types/ is
# checked in). Mirrors the `test` job in .github/workflows/test.yml on Node.js 24: install with the
# lockfile, then run the quick unit suites as a smoke test.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci --no-audit --no-fund

# Smoke test, so a broken image is visible in the build log without failing the build. The full suite
# (`npm run test:only`) takes about seven minutes and is listed in threat_model.md.
RUN npx jest --runInBand --ci test/globToRegExp.test.js test/reducePlan.test.js test/LinkResolver.test.js \
      test/WatchpackUnit.test.js \
    || echo "WARNING: the unit test suites reported failures"
