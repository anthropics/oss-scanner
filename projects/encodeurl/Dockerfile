# encodeurl: percent-encodes a URL for safe use in HTTP headers such as Location and Content-Location, leaving
# existing percent-encoding and already-safe characters alone; used by express (`res.redirect()`, `res.location()`),
# send, serve-static and finalhandler. Since 3.0 it is TypeScript built with @borderless/ts-scripts. Built and tested
# the way its CI (.github/workflows/ci.yml) does: npm ci, then `npm test` (vitest specs plus a size-limit check on
# dist/). CI covers Node 22 and latest; the scanner uses the current LTS.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# package-lock.json is committed, so install exactly the locked dependencies. Lifecycle scripts stay enabled on
# purpose: the package's own `prepare` script (`ts-scripts install && npm run build`) compiles src/ into dist/,
# which the tests and the size-limit check need.
RUN npm config set loglevel error && npm ci

# The vitest suite and the dist/ size check. A failing test should not abort the image build; the scanner runs
# them again offline.
RUN npm test || echo "WARNING: npm test reported failures"
