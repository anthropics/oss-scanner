FROM golang:1.26.6-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make wget \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN for i in 1 2 3; do go mod download && break; sleep 10; done && go mod download

# build/cometbft as the Makefile builds it, but unstripped so debuggers have symbols, plus abci-cli and every package.
RUN make build COMETBFT_BUILD_OPTIONS=nostrip \
    && make install_abci \
    && go build ./...

# Compile every test binary, including the deadlock, race and release variants, so offline runs only relink.
RUN go test -run '^$' ./... \
    && go test -tags deadlock -run '^$' ./... \
    && go test -race -run '^$' ./... \
    && go test -tags release -run '^$' ./rpc/jsonrpc/client/

RUN (go test -p 2 -timeout 15m -tags deadlock \
        ./types/... ./crypto/... ./mempool/... ./consensus/propagation/... ./p2p/conn/... \
        ./blocksync/... ./statesync/... ./evidence/... ./light/... ./privval/... ./test/fuzz/... \
        || echo "WARNING: go test reported failures") \
    && git status --short

ENV GOPROXY=off \
    GOFLAGS=-mod=readonly
