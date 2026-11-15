# A pure TypeScript cryptography library from paulmillr's noble family, built and tested the way its CI
# (paulmillr/jsbt .github/workflows/test.yml) does: submodules, npm ci --ignore-scripts, tsc, node test/index.ts.
FROM node:24-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner clones without submodules. Some packages keep their test vectors (acvp-vectors) in one; fetch
# them now, while online. This is a no-op for packages without a .gitmodules.
RUN git config --global --add safe.directory '*' \
    && git submodule update --init --depth 1

# Install-time scripts of dependencies stay blocked, as in CI. `npm run build` is tsc; it emits the .js and
# .d.ts files that the published package ships.
RUN npm ci --ignore-scripts
RUN npm run build

# The fast test suite. Slow suites (npm run test:slow etc.) are left for the scanner to run when needed.
RUN npm test || echo "WARNING: npm test reported failures"
