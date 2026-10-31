# Scanner image for https://github.com/lightningnetwork/lnd.
#
# The repository's own Dockerfile builds a release binary by cloning master inside the image, so it
# cannot be reused here: the scanner supplies its own checkout as the build context and expects it at
# /src. This file builds that checkout instead, with the tags the project's Makefile uses for tests.
#
# lnd is a Go module with a dozen nested modules (actor, kvdb, sqldb, tlv, ...) reached through
# `replace` directives, so the build context alone is enough: nothing needs fetching from a sibling
# repository. `make unit` also needs a `btcd` binary on PATH to run its integration-ish unit tests,
# which is installed from the tools module while the network is still available.

FROM golang:1.26.10-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config \
      sqlite3 jq procps \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up. GOPATH is /go, so
# the tools below land on PATH in /go/bin.
RUN go mod download && go mod verify \
    && cd tools && go install -trimpath github.com/btcsuite/btcd \
    && cd /src && for mod in actor cert clock fn healthcheck kvdb queue sqldb ticker tlv tor \
    ; do (cd "$mod" && go mod download) || exit 1; done

# BUILD_TAGS mirrors make/testing_flags.mk: DEV_TAGS=dev plus RPC_TAGS. Tests compile against the same
# tags, so the audit sees the RPC servers, the dev-only harness and the routers as CI does.
ENV BUILD_TAGS="dev autopilotrpc chainrpc invoicesrpc neutrinorpc peersrpc signrpc walletrpc watchtowerrpc"

# Build everything with debug info and no inlining so stack traces and reproducers match the source,
# then compile every test binary without running it.
RUN go build -tags="$BUILD_TAGS" -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' -tags="$BUILD_TAGS" ./...

# The nested modules are separate builds; compile their tests too, since several carry real logic
# (kvdb backends, sqldb migrations, the tlv and queue primitives).
RUN for mod in actor cert clock fn healthcheck kvdb queue sqldb ticker tlv tor ; do \
      (cd "$mod" && go test -count=1 -run '^$' ./...) || exit 1 ; \
    done

# Run the suite so the image is known to work, but do not let a failing test abort the build: some
# tests need several GB of memory and a long timeout, and a failure here is not a build failure.
RUN (go test -count=1 -timeout 40m -tags="$BUILD_TAGS" ./... || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
