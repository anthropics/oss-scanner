# multer: Express middleware for multipart/form-data uploads, built on busboy: it parses fields and files,
# enforces limits, and stores files in memory or on disk through pluggable storage engines. Built and tested the
# way its CI (.github/workflows/ci.yml) does: npm install, then `npm run test-ci` (nyc over mocha). CI covers
# Node 10.16 through current; the scanner uses the current LTS. There is no lockfile, so dependencies resolve to
# the latest versions allowed by package.json, exactly as in CI.
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
# The tests feed multipart bodies through in-process streams and HTTP servers on local ports only, and write
# temporary files under the OS temp directory.
RUN npm run test-ci || echo "WARNING: npm run test-ci reported failures"
