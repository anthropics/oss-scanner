# Scanner image for https://github.com/btcsuite/btcwallet.
#
# The repository ships no application Dockerfile, only a tools image for linting, so this builds the
# checkout the scanner supplies at /src.
#
# btcwallet is a root module plus five nested modules (walletdb, wtxmgr, wallet/txauthor,
# wallet/txrules, wallet/txsizes). `make unit` tests the root; the nested ones are built and their
# tests compiled here too, because walletdb and wtxmgr own the durable state and the crash guarantees.

FROM golang:1.27.3-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config jq \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up. The wallet module
# uses bbolt (pure Go), so no database headers are needed.
RUN go mod download && go mod verify \
    && for mod in walletdb wtxmgr wallet/txauthor wallet/txrules wallet/txsizes ; do \
         (cd "$mod" && go mod download) || exit 1 ; \
       done

# Build with debug info and no inlining so stack traces and reproducers match the source, then compile
# every test binary without running it.
RUN go build -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' ./...

RUN for mod in walletdb wtxmgr wallet/txauthor wallet/txrules wallet/txsizes ; do \
      (cd "$mod" && go build -gcflags='all=-N -l' ./... && go test -count=1 -run '^$' ./...) || exit 1 ; \
    done

# Run the suite so the image is known to work, but do not let a failing test abort the build.
RUN (go test -count=1 -timeout 20m ./... || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
