# type-is: checks whether a request's Content-Type matches a set of expected types (`typeis(req, ['json'])`),
# used by body-parser, express, koa and multer to decide which parser handles a body. Since 3.0 it is TypeScript
# built with @borderless/ts-scripts. Built and tested the way its CI (.github/workflows/ci.yml) does: npm ci,
# then `npm test` (vitest specs). CI covers Node 22 and latest; the scanner uses the current LTS.
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
# which consumers import.
RUN npm config set loglevel error && npm ci

# The vitest suite. A failing test should not abort the image build; the scanner runs them again offline.
RUN npm test || echo "WARNING: npm test reported failures"
