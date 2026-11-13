# OSS Scanner build for xrpl.js (https://github.com/XRPLF/xrpl.js): npm/lerna monorepo with the `xrpl` client
# library and its codec, keypair and address packages. Mirrors the repo's CI (.github/workflows/nodejs.yml).
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to
# .oss-scanner/Dockerfile in a fresh clone of xrpl.js and builds it with that clone as the build context. The
# network is available only while this file builds, so every dependency must be fetched here.
FROM node:22-bookworm
ENV CI=true

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci
# Build every package (TypeScript to dist/, plus the web bundles).
RUN npm run build

# mpt-crypto vendors a WASM module that is normally fetched at release time. Fetch it now, while the network is
# up, so code that loads it can run offline. A failed fetch is logged, not fatal.
RUN npm run fetch:wasm --workspace=@xrplf/mpt-crypto || echo "WARNING: mpt-crypto WASM fetch failed"

# Run every package's unit tests (not the browser or integration tests, which need Chrome or a ledger). Failures are
# logged, not fatal.
RUN npm test --workspaces --if-present \
    || echo "WARNING: unit tests reported failures"
