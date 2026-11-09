# Builds GuideChimp the way its release workflow does: Node + npm ci, `npm run build` (Vite/Sass bundle into dist/),
# then the Vitest suite. All npm packages are fetched here, while the network is up.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl build-essential python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci
RUN npm run build
# Cheap tests, so a broken image is visible in the build log without failing the build.
RUN (npm run test || echo "WARNING: vitest reported failures")
RUN (npm run lint || echo "WARNING: eslint reported findings")
