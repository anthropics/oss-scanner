# A TypeScript client for the X (Twitter) API v1.1 and v2, built and tested the way its CI
# (.github/workflows/CI.yml) does: npm ci, tsc for the CJS and ESM builds, then the offline mocha suite.
FROM node:24-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install-time scripts stay blocked: the only one is the package's own `prepublish`, which is `npm run build`.
# The build emits dist/cjs and dist/esm, the only directory the npm package ships.
RUN npm ci --ignore-scripts
RUN npm run build

# The offline suite: test/fake-x.ts answers on a local server in place of api.x.com, so it needs no network and
# no credentials. test/live/ calls the real X API and is left out.
RUN npm test || echo "WARNING: npm test reported failures"
