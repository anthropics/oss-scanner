# mime-db: the media type database used by mime-types and, through it, by Express and most of the Node.js
# ecosystem. Built and tested the way its CI (.github/workflows/ci.yml) does: npm install, then mocha (`npm test`).
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

# The unit tests validate db.json. A failing test should not abort the image build; the scanner runs them again
# offline. `npm run fetch` (regenerating the database from IANA, Apache and nginx) needs the network and is not run.
RUN npm test || echo "WARNING: npm test reported failures"
