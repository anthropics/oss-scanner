# multiparty: a streaming multipart/form-data parser (fields and files, with limits) that can hand each part to
# the application as a stream or write files to a temporary directory. Built and tested the way its CI
# (.github/workflows/ci.yml) does: npm install, then mocha (`npm test`). CI covers Node 0.10 through current;
# the scanner uses the current LTS. There is no lockfile, so dependencies resolve to the latest versions
# allowed by package.json, exactly as in CI.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_OPTIONS=--dns-result-order=ipv4first
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install-time scripts of dependencies stay blocked, as in CI.
RUN npm config set loglevel error && npm install --ignore-scripts

# The unit tests. A failing test should not abort the image build; the scanner runs them again offline.
# The tests replay the multipart fixtures under test/fixture through in-process parsers and HTTP servers on
# local ports only, and write temporary files under the OS temp directory. NODE_OPTIONS above makes `localhost`
# resolve to 127.0.0.1 for both listen and connect inside the container (the "connection aborted closed" test
# otherwise gets ECONNREFUSED across address families and mocha then hangs on the open server handle); the
# timeout is a belt-and-braces guard so a hung test run can never block the image build.
RUN timeout 900 npm test || echo "WARNING: npm test reported failures"
