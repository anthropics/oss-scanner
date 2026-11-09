# Build context is the upstream facebook/react-native repository.
# Scope: the JS/Node packages (dev server middleware, CLI plugin, codegen, runtime JS).
# Android/iOS native builds are not done here; native sources are present for review only.
FROM node:24-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
ENV CI=true

COPY . /src
WORKDIR /src

RUN yarn install --non-interactive --frozen-lockfile

# Compile the Node packages (dev-middleware, community-cli-plugin, etc.) to dist/.
RUN yarn build

# Cheap smoke tests; failures don't abort the image.
RUN yarn jest --ci --silent packages/dev-middleware packages/community-cli-plugin \
    || echo "WARNING: tests reported failures"
CMD ["bash"]
