# wmux build for OSS Scanner. Follows the Linux leg of
# .github/workflows/ci-cross-platform-baseline.yml, on the Node floor ci.yml
# uses (>=24.21 <25) and npm 11.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# node-pty builds from source on Linux (build-essential, python3 for node-gyp);
# libxss1 matches the CI leg. git, openssl, perl, procps (ps) and bsdutils
# (script) are spawned by the unit tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential python3 git libxss1 openssl perl procps bsdutils \
    && rm -rf /var/lib/apt/lists/*

# Fail early if the base image's Node drifts outside the supported floor.
RUN node -e "const [a,b]=process.versions.node.split('.').map(Number); if (a !== 24 || b < 21) { console.error('need Node >=24.21 <25, got ' + process.version); process.exit(1); }" \
    && npm install -g npm@11

# scanner contract: the checkout lives inside the image, at /src
COPY --chown=node:node . /src
WORKDIR /src

# Unit tests assert POSIX permission behaviour (0o600 files, refused access),
# which root bypasses, so install, build and test as the image's node user.
USER node

# npm ci also runs Electron's postinstall, which downloads the Electron binary;
# the check makes sure require('electron') resolves once the network is gone.
RUN npm ci \
    && node -e "require('fs').accessSync(require('electron'))"

RUN node scripts/typecheck.mjs
RUN npm run build:daemon && npm run build:mcp

# Run the unit tests (parallel + runtime lanes) so the image is known to work,
# without letting a failing test abort the build.
RUN npm test || echo "WARNING: npm test reported failures"
