# Lodash: a JavaScript utility library, built and tested the way its CI (.github/workflows/ci-node.yml) does:
# npm install, then `npm run validate` (jscs style checks + npm test). `npm test` runs `npm run build` first
# (pretest), which regenerates dist/ and the fp/ builds from lodash.js, then runs test/test.js and test/test-fp.js.
# CI covers Node 4 through 25; the scanner uses the current LTS.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# package-lock.json is committed, so install exactly the locked dev dependencies. Install-time scripts of
# dependencies stay blocked; nothing lodash needs relies on them.
RUN npm ci --ignore-scripts

# Rebuild dist/ and fp/ from lodash.js, as `npm test` would.
RUN npm run build

# The unit tests. A failing test should not abort the image build; the scanner runs them again offline.
RUN npm test || echo "WARNING: npm test reported failures"
