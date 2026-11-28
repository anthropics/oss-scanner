# enhanced-resolve: a single-package npm repository with no build step (lib/ is plain CommonJS and types/
# is committed). Mirrors the Node 22+ legs of the `test` job in .github/workflows/test.yml: install with the
# lockfile, then run the node:test suite as a smoke test.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# test/simple.test.js expects the checkout to be named enhanced-resolve.
RUN ln -s /src /enhanced-resolve

RUN npm ci --no-audit --no-fund

# Smoke test, so a broken image is visible in the build log without failing the build. `npm test` would
# run the linters first (pretest); the other commands are listed in threat_model.md.
RUN npm run test:only || echo "WARNING: test:only reported failures"
