# webpack: a single-package Yarn 1 (classic) repository. Mirrors the `basic` and `integration` jobs in
# .github/workflows/test.yml: install with a frozen lockfile, link webpack into its own node_modules (the
# test suite requires "webpack" by name), then run the cheap basic suite as a smoke test.
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

# Spec corpora for the test262, html5lib, css-parsing and terser-based minifier suites, fetched one commit
# deep while the network is up. test/external/wpt (161k files), swc and oxc are left out: the suites that
# read them (syntax-equivalence, minify-corpora) are not meant to be run in this image.
RUN node tooling/retry.js git submodule update --init --depth 1 \
      test/external/test262-cases test/external/html5lib-tests test/external/css-parsing-tests \
      test/external/terser \
    || echo "WARNING: could not fetch the spec corpora submodules"

# The official node image ships Yarn 1, which is what package.json's packageManager field pins.
RUN node tooling/retry.js yarn --frozen-lockfile
RUN yarn link --frozen-lockfile || true
RUN yarn link webpack --frozen-lockfile

# Smoke test, so a broken image is visible in the build log without failing the build. `yarn test` would
# run the linters first (pretest); the other suites are listed in threat_model.md.
RUN yarn test:basic --ci || echo "WARNING: test:basic reported failures"
