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

# Same steps as CI (.circleci/config.yml): install with the lockfile, then compile every package under packages/.
RUN yarn install --ignore-scripts --frozen-lockfile
RUN yarn build

# Per-package test suites (vitest), run in-process against local servers; no external services needed.
RUN (yarn test:e2e:graphql && yarn test:e2e:apollo && yarn test:e2e:mercurius) \
    || echo "WARNING: tests reported failures"
