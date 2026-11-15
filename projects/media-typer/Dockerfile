# media-typer: parses and formats media type strings such as `application/vnd.api+json` into type, subtype and
# suffix (RFC 6838), used by type-is, body-parser and compressible. Since 2.0 it is TypeScript built with
# @borderless/ts-scripts. Built and tested the way its CI (.github/workflows/ci.yml) does: npm ci, then `npm test`
# (vitest specs plus a size-limit check on dist/). CI covers Node 18 through current; the scanner uses the current LTS.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# package-lock.json is committed, so install exactly the locked dependencies. Lifecycle scripts stay enabled:
# the package's own `prepare` script installs the ts-scripts tooling.
RUN npm config set loglevel error && npm ci

# Compile src/ into dist/, which is what consumers import and what the size-limit check measures. The package only
# builds on publish (`prepublishOnly`), so run it explicitly here.
RUN npm run build

# The vitest suite and the dist/ size check. A failing test should not abort the image build; the scanner runs
# them again offline.
RUN npm test || echo "WARNING: npm test reported failures"
