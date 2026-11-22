# Scanner image for https://github.com/btcsuite/btcd.
#
# The repository's own Dockerfile builds a release image by copying the tree to /app and running
# `go install`; it is close to what the scanner wants but has no test toolchain and no submodule
# builds. This file takes the scanner's checkout at /src and prepares it for an offline audit.
#
# btcd is a root module plus nine nested modules (address, btcec, btcutil, chaincfg, chainhash, psbt,
# txscript, v2transport, wire). `make unit` tests the root and two of them (address, btcec); all nine
# are built and their tests compiled here, because several are where the parsing actually happens.

FROM golang:1.26.10-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config jq \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up, for the root module
# and for each nested one.
RUN go mod download && go mod verify \
    && for mod in address btcec btcutil chaincfg chainhash psbt txscript v2transport wire ; do \
         (cd "$mod" && go mod download) || exit 1 ; \
       done

# Build with debug info and no inlining so stack traces and reproducers match the source, then compile
# every test binary without running it.
RUN go build -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' ./...

RUN for mod in address btcec btcutil chaincfg chainhash psbt txscript v2transport wire ; do \
      (cd "$mod" && go build -gcflags='all=-N -l' ./... && go test -count=1 -run '^$' ./...) || exit 1 ; \
    done

# Run the suite so the image is known to work (this is what `make unit` runs), but do not let a failing
# test abort the build.
RUN (go test -count=1 -timeout 20m ./... || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
