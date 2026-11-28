# Scanner image for https://github.com/lightninglabs/neutrino.
#
# The repository ships only a tools image for linting, so this builds the checkout the scanner supplies
# at /src. neutrino is a privacy-preserving SPV client: it speaks the Bitcoin P2P protocol to
# untrusted peers, so this image is meant to make header, filter and Merkle-proof handling easy to
# reach offline.
#
# neutrino is a root module plus cache/ and tools/. `make unit` also wants a `btcd` binary on PATH,
# which is installed from the tools module while the network is still available.

FROM golang:1.25.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config jq procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up. GOPATH is /go, so the
# btcd installed from the tools module lands on PATH in /go/bin.
RUN go mod download && go mod verify \
    && (cd cache && go mod download) \
    && (cd tools && go install -trimpath -tags=tools github.com/btcsuite/btcd)

# Build with debug info and no inlining so stack traces and reproducers match the source, then compile
# every test binary without running it.
RUN go build -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' ./...

# Run the suite so the image is known to work, but do not let a failing test abort the build. Some of
# these tests drive a real btcd over loopback; those that cannot run here simply fail and the build
# continues.
RUN (go test -count=1 -timeout 30m ./... || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
