# syntax=docker/dockerfile:1
# Build context: only the public marionettejs/marionette checkout, not this repo
# or the host workspace. Source lives at /src for the scanner contract.
# Toolchain matches .nvmrc and config/release-profile.json inspected on master
# at 909890031209404fd8a375447abf51cc3a35ebfe (2026-10-20).
FROM node:24.19.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
    npm_config_audit=false \
    npm_config_fund=false \
    npm_config_update_notifier=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global npm@11.17.0

COPY . /src
WORKDIR /src

# Fetch locked dependencies without executing dependency lifecycle scripts.
# The inspected lockfile's only install-script package is optional macOS-only
# fsevents. Run the project's own prepare explicitly in the offline step below.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npx --no-install playwright install --with-deps --only-shell --no-progress chromium firefox webkit \
    && chmod -R a+rX /opt/playwright-browsers

# prepare builds all five first-party packages, declarations, packaged docs and
# distribution checks. Fail visibly on build or test errors; do not mask them.
# BuildKit's network isolation verifies the principal audit commands offline.
RUN --network=none npm run check:release-profile \
    && npm run check:browser-profile \
    && npm run prepare \
    && npm run test:source \
    && npm test

# The browser development-kit test creates a temporary consumer project and
# resolves its own pinned tooling. Warm its npm cache while online, then force
# npm to use that cache for the complete offline browser suite.
RUN npm run test:browser -- --project=chromium test/browser/development-kit.spec.mjs
RUN --network=none npm_config_offline=true npm run test:browser

# Keep source, node_modules, built packages and browser binaries for offline
# reproduction. No credentials, host mounts or publishing steps are required.
CMD ["bash"]
