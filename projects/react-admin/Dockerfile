# Build context is the upstream marmelab/react-admin repository.
FROM node:22-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
ENV CI=true HUSKY=0 CYPRESS_INSTALL_BINARY=0 PUPPETEER_SKIP_DOWNLOAD=1

COPY . /src
WORKDIR /src

# The repository pins Yarn through .yarnrc.yml (yarnPath), so the global yarn delegates to it.
RUN yarn install --immutable
RUN make build

RUN yarn test-unit --maxWorkers=50% || echo "WARNING: unit tests reported failures"
CMD ["bash"]
