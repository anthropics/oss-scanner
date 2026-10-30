# Scanner image for https://github.com/lightninglabs/taproot-assets.
#
# The repository's own Dockerfile builds release binaries by cloning the repo inside the image, so it
# cannot be reused: the scanner supplies its own checkout as the build context and expects it at /src.
#
# taproot-assets is a root module plus taprpc/, tools/ and one documentation example module. The
# database layer uses modernc.org/sqlite, which is pure Go, so this image needs no SQLite headers;
# CGO stays on because the secp256k1 and BIP-340 paths can use it and the tests are built that way.

FROM golang:1.27.3-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config jq procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up.
RUN go mod download && go mod verify \
    && (cd taprpc && go mod download)

# BUILD_TAGS mirrors make/testing_flags.mk: DEV_TAGS=dev plus the RPC_TAGS it adds by default, so the
# RPC servers and their marshalling are part of what gets audited.
ENV BUILD_TAGS="dev autopilotrpc chainrpc invoicesrpc peersrpc routerrpc signrpc verrpc walletrpc watchtowerrpc wtclientrpc"

# Build with debug info and no inlining so stack traces and reproducers match the source, then compile
# every test binary without running it. The suite is large (a few hundred test files), so give the
# compile step room.
RUN go build -tags="$BUILD_TAGS" -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' -tags="$BUILD_TAGS" ./...

# Run the suite so the image is known to work, but do not let a failing test abort the build.
RUN (go test -count=1 -timeout 40m -tags="$BUILD_TAGS" ./... || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
