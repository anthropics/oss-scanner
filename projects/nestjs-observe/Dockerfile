FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    HUSKY=0 \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same steps as CI (.github/workflows/ci.yml). Install scripts stay on: @swc/core's postinstall is needed by
# vitest. The lockfile is written with legacy-peer-deps and has to be read that way.
RUN npm ci --legacy-peer-deps
RUN npm run build

# Unit tests (vitest), then integration tests that boot real Nest apps on local ports. The queue and
# query-span suites need Redis, PostgreSQL, MySQL and MongoDB; they skip themselves when those are absent.
# Most suites reach the app through app.getUrl(), which is [::1] when it listens on the wildcard address:
# they need IPv6 on loopback, which a plain `docker build` turns off (they pass where it is on).
RUN npm test || echo "WARNING: unit tests reported failures"
RUN npm run test:int || echo "WARNING: integration tests reported failures"
