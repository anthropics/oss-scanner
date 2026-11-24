# Builds G1-Warrant control plane and caches all Go & UI dependencies for offline analysis
FROM docker.io/library/golang:latest

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      make \
      openssl \
      jq \
      procps \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 for embedded console UI compilation
COPY --from=docker.io/library/node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=docker.io/library/node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && node --version && npm --version

COPY . /src
WORKDIR /src

# Download Go module dependencies while online
RUN go mod download

# Build embedded console UI
RUN if [ -d "web" ]; then cd web && npm ci && npm run build && cd ..; fi

# Compile all Go binaries and packages so caches are populated
RUN go build ./...

# Baseline fast tests (non-database / unit)
RUN go test -short ./... || echo "WARNING: baseline Go tests reported failures"

# Air-gap Go module fetching for subsequent analysis
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
