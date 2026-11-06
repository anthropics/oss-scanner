# Builds openapi-client-axios for Anthropic's OSS Scanner.
# Network is available during this build only; the scan runs offline. Mirrors .github/workflows/ci.yml.
FROM node:20-bookworm
ENV CI=true \
    NODE_ENV=development

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# npm ci runs the `prepare` script, which is `tsc`. Output lands next to package.json (index.js, client.js,
# query-serializer.js, with .d.ts and source maps). The explicit build is a no-op safety net.
RUN npm ci && npm run build

# jest suite; HTTP is mocked with msw, so it runs offline. A failing test must not abort the build.
RUN (timeout 900 npm test || echo "WARNING: jest reported failures")
