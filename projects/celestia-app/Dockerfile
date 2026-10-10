FROM golang:1.26.6-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make wget \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN for i in 1 2 3; do go mod download && break; sleep 10; done && go mod download

# Multiplexer build (embeds the checksum-verified v3-v9 release binaries) and the fibre server.
RUN make build build-fibre-server

# Compile every test binary, including the multiplexer and benchmark tags, so offline runs only relink.
RUN go test -run '^$' ./... \
    && go test -tags multiplexer -run '^$' ./multiplexer/... ./cmd/celestia-appd/cmd \
    && go test -tags benchmarks -run '^$' ./app/benchmarks/...

RUN (make test-short || echo "WARNING: make test-short reported failures") \
    && (go test -tags multiplexer ./multiplexer/... ./cmd/celestia-appd/cmd \
        || echo "WARNING: multiplexer tests reported failures") \
    && git status --short

ENV GOPROXY=off \
    GOFLAGS=-mod=readonly
