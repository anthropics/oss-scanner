FROM node:22-bookworm AS node
FROM golang:1.25.13-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install --global pnpm@11.9.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git make python3 curl jq \
      iproute2 nftables dnsmasq-base ppp wireguard-tools openssl \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src
RUN go mod download && go mod verify
# Keep debug symbols in the audit binaries; do not build or install a release ISO.
RUN make build build-mcp GO_LDFLAGS= \
    && go test -race -run '^$' ./...
RUN pnpm --dir web install --frozen-lockfile \
    && pnpm --dir web build \
    && pnpm --dir web exec playwright install --with-deps chromium webkit

CMD ["bash"]
