# http-errors: creates HTTP error objects (`createError(404, ...)`) with status, message, `expose` and `headers`,
# used by body-parser, send, finalhandler, express, koa and most of the Node.js ecosystem. Built and tested the
# way its CI (.github/workflows/ci.yml) does: npm install, then mocha (`npm test`). CI covers Node 0.8 through
# current; the scanner uses the current LTS. There is no lockfile, so dependencies resolve to the latest versions
# allowed by package.json, exactly as in CI.
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
RUN npm test || echo "WARNING: npm test reported failures"
