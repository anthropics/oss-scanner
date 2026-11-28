# webpack-dev-server: a single-package npm repository. Mirrors the `test` job in .github/workflows/nodejs.yml:
# install with the lockfile, build (CJS output in dist/, the client shims in client/, types/), install a
# browser for the Puppeteer-driven e2e tests, link the package into its own node_modules, then run a cheap
# smoke test.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Debian's Chromium stands in for CI's Chrome for Testing, for the Puppeteer-driven e2e suites.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci
RUN npm run build

RUN cp -R client tmp-client \
    && (npm link --ignore-scripts || true) \
    && (npm link webpack-dev-server --ignore-scripts || true) \
    && rm -r client && mv tmp-client client

# Smoke test, so a broken image is visible in the build log without failing the build. `npm test` would run
# the linters first (pretest); the other suites are listed in threat_model.md.
RUN node --import ./scripts/node-test-setup.mjs --experimental-test-module-mocks --test --test-force-exit \
      test/validate-options.test.js test/normalize-options.test.js \
    || echo "WARNING: the option tests reported failures"
