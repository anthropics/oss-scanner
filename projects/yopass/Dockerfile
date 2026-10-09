# Keep the source, toolchains, dependency caches and test browsers available
# for the scanner, which runs without Internet access after this build.
FROM node:24-bookworm AS node
FROM golang:1.27-bookworm

COPY --from=node /usr/local/ /usr/local/
COPY --from=node /opt/ /opt/
ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    GOWORK=off \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 memcached redis-server \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the complete checkout must remain at /src.
COPY . /src
WORKDIR /src
RUN go mod download \
    && go build -o /usr/local/bin/yopass ./cmd/yopass \
    && go build -o /usr/local/bin/yopass-server ./cmd/yopass-server
RUN cd deploy/cdk && go mod download && go build ./...

WORKDIR /src/website
RUN yarn install --frozen-lockfile --network-timeout 600000 \
    && yarn playwright install --with-deps chromium firefox webkit \
    && yarn build

# The server serves the compiled frontend from this path by default.
RUN mkdir -p /src/public && cp -a dist/. /src/public/

# Run the tests that need no external services during setup. The threat model
# documents how to start local backends and run integration tests offline.
RUN yarn test:unit
WORKDIR /src
RUN go test ./cmd/... ./pkg/...
CMD ["bash"]
