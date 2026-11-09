# Build context is the upstream facebook/react repository.
FROM node:24-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 make g++ default-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV CI=true

COPY . /src
WORKDIR /src

# Root workspace only (compiler/ is a separate yarn project and out of scope).
RUN yarn install --frozen-lockfile

# Build the in-scope Node bundles (dev + prod, experimental channel) into build/node_modules.
RUN RELEASE_CHANNEL=experimental node ./scripts/rollup/build.js \
      react/,react-dom,react-server,react-client,scheduler --type=NODE_DEV,NODE_PROD

# Cheap smoke tests; failures don't abort the image.
RUN yarn test --ci --silent \
      packages/react-dom/src/__tests__/ReactDOMServerIntegrationAttributes-test.js \
      packages/react-server-dom-webpack/src/__tests__/ReactFlightDOMReply-test.js \
      packages/react-dom/src/__tests__/ReactDOMServerIntegrationUntrustedURL-test.js \
    || echo "WARNING: tests reported failures"
CMD ["bash"]
