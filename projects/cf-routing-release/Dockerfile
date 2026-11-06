# Builds cloudfoundry/routing-release like its BOSH packaging (packages/*/packaging): one vendored Go module at
# src/code.cloudfoundry.org, built with the Go toolchain develop pins (Go 1.27). Vendored => no network needed.
FROM golang:1.27-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
# a BOSH release: the single Go module is one level down
WORKDIR /src/src/code.cloudfoundry.org

# Build each shipped binary by import path, as packages/*/packaging does (routing-api is vendored but still
# shipped). -gcflags "-N -l" keeps debug info and skips inlining so the auditor gets readable stack traces.
ENV GOFLAGS="-mod=vendor"
RUN set -eux; mkdir -p /out/bin; \
    build() { go build -gcflags=all="-N -l" -o "/out/bin/$1" "code.cloudfoundry.org/$2"; }; \
    build gorouter             gorouter/cmd/gorouter; \
    build gorouter-cfgcheck    gorouter/cmd/config-validator; \
    build routing-api          routing-api/cmd/routing-api; \
    build routing-api-cfgcheck routing-api/cmd/config-validator; \
    build cf-tcp-router        cf-tcp-router/cmd/cf-tcp-router; \
    build tcp-router-cfgcheck  cf-tcp-router/cmd/config-validator; \
    build route-registrar      route-registrar; \
    build rtr                  routing-api-cli

# Warm caches for the offline audit. Not `go test`: the integration/cmd suites need external daemons (NATS,
# HAProxy, Consul) the networkless scan VM lacks. `go vet` compiles packages + tests without running them.
RUN go build ./... || echo "WARNING: go build reported errors"
RUN go vet ./...  || echo "WARNING: go vet reported findings"
