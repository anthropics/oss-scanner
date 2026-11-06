# Scan image for the Nezha Agent source repository, not a production service image.
FROM golang:1.26.6-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Match upstream CI: TestLookupIP explicitly opts out of live public-DNS probes in CI.
# No source/tests are changed; the remaining ordinary suite runs with no network.
ENV CI=true

# Preserve source, module dependencies, the toolchain and an executable for offline auditing.
RUN git rev-parse HEAD && go version \
    && go mod download \
    && mkdir -p /src/build \
    && go build -mod=readonly -o /src/build/nezha-agent ./cmd/agent

# In the scanner's offline shell: go test -mod=readonly -count=1 ./...
