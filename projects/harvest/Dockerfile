# NetApp Harvest: a Go collector that polls ONTAP, StorageGRID, E-Series, and Cisco switches
# and exports metrics to Prometheus/InfluxDB. The checkout lives at /src.
FROM golang:1.27.2

ENV GOTOOLCHAIN=local

COPY . /src
WORKDIR /src

# The root module vendors its dependencies. The mcp module does not, so fetch its modules
# now while the network is available.
RUN cd mcp && go mod download

# Build the harvest and poller binaries the way `make harvest` does, keeping debug info.
RUN mkdir -p bin && go build -trimpath -o bin ./cmd/harvest ./cmd/poller \
    && cd mcp && go build -o bin/harvest-mcp ./cmd/server

# Warm the build and test caches so tests can run offline. Failures do not abort the build.
RUN (go test -race -count=1 ./... || echo "WARNING: go test reported failures") \
    && (cd mcp && go test -race -count=1 ./... || echo "WARNING: mcp go test reported failures")
