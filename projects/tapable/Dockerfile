# tapable: a single-package npm repository with a package-lock.json (lockfileVersion 3). Mirrors the
# `test` job in .github/workflows/test.yml on current Node.js: install with `npm ci`, then run Jest.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci --no-audit --no-fund

# Smoke test, so a broken image is visible in the build log without failing the build. `npm run lint` and
# `npm run benchmark` are listed in threat_model.md.
RUN npx jest --ci || echo "WARNING: jest reported failures"
