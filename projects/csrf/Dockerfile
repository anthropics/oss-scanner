# csrf: the token primitive behind csurf and similar middleware: generates a per-session secret, derives
# cross-site request forgery tokens from it with a salt and SHA-1, and verifies tokens in constant time.
# Built and tested the way its CI (.github/workflows/ci.yml) does: npm install, then mocha (`npm test`).
# CI covers Node 0.8 through current; the scanner uses the current LTS. There is no lockfile, so dependencies
# resolve to the latest versions allowed by package.json, exactly as in CI.
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
