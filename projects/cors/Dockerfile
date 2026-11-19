# cors: Express/Connect middleware that answers Cross-Origin Resource Sharing preflight requests and sets the
# Access-Control-* response headers from the application's configuration. Built and tested the way its CI
# (.github/workflows/ci.yml) does: npm install, then `npm run test-ci` (nyc over mocha; `npm test` additionally
# runs eslint, which CI does in a separate step). CI covers Node 0.10 through current; the scanner uses the
# current LTS. There is no lockfile, so dependencies resolve to the latest versions allowed by package.json,
# exactly as in CI.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install-time scripts of dependencies stay blocked, as in CI.
RUN npm config set loglevel error && npm install --ignore-scripts

# The unit tests. A failing test should not abort the image build; the scanner runs them again offline.
# The tests use in-process HTTP servers on local ports only, so they work without network access.
RUN npm run test-ci || echo "WARNING: npm run test-ci reported failures"
