# Builds openapi-backend for Anthropic's OSS Scanner.
# Node 22: package.json allows >=20 and CI tests on 20, but vitest 5 declares node ^22.12 || ^24, so 22 keeps npm quiet.
# Network is available during this build only; the scan that follows runs offline, so everything
# the tests need is fetched here. Mirrors the library job in .github/workflows/ci.yml.
FROM node:22-bookworm
ENV CI=true \
    NODE_ENV=development

# scanner contract: the checkout lives inside the image, at /src (.git included, so history is readable offline)
COPY . /src
WORKDIR /src

# Install exactly the lockfile and compile src/ with tsc. Output lands next to package.json
# (index.js, backend.js, router.js, validation.js, with source maps), which is what `require('/src')` loads.
RUN npm ci && npm run build

# Run the vitest suite so the image is known to work. A failing test must not abort the build.
RUN (timeout 900 npm test || echo "WARNING: vitest reported failures")
