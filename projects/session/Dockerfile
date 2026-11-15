# express-session (repository expressjs/session): server-side session middleware for Express: issues a signed
# session-id cookie, loads and saves session data through a pluggable store (MemoryStore built in), and controls
# cookie attributes, rolling, resave and regeneration. Built and tested the way its CI (.github/workflows/ci.yml)
# does: npm install, then `npm test`, whose script first runs test/support/gencert.sh (openssl, self-signed
# certificate for the HTTPS tests) and then mocha. CI covers Node 0.8 through current; the scanner uses the
# current LTS. There is no lockfile, so dependencies resolve to the latest versions allowed by package.json,
# exactly as in CI.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git openssl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install-time scripts of dependencies stay blocked, as in CI.
RUN npm config set loglevel error && npm install --ignore-scripts

# Generate the test certificate once, during the build, so the fixture exists when the scanner runs the tests
# offline (the script only needs the local openssl binary, but running it here keeps the image self-contained).
RUN sh ./test/support/gencert.sh

# The unit tests. A failing test should not abort the image build; the scanner runs them again offline.
# The tests use in-process HTTP and HTTPS servers on local ports only.
RUN npm test || echo "WARNING: npm test reported failures"
