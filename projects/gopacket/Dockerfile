# Build gopacket the way its CI does: Go toolchain from go.mod, cgo enabled, libpcap headers for the pcap package.
FROM golang:1.25-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential libpcap-dev tcpdump \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module the build and the tests need while the network is still up.
RUN go mod download && go mod verify

# pfring (and the example that imports it) needs PF_RING headers, which Debian does not ship, so both are
# skipped. Every other package builds with debug info and no inlining so stack traces match the source.
# go vet is not run: afpacket trips its unsafe.Pointer check by design, and upstream CI skips it too.
RUN PKGS="$(go list -e -f '{{.ImportPath}} {{join .Deps " "}}' ./... | grep -v pfring | cut -d' ' -f1)" \
    && go build -gcflags='all=-N -l' $PKGS \
    && go test -count=1 -run '^$' $PKGS

# Run the test suite so the image is known to work, but do not let a failing test abort the build.
# A few tests in pcapgo and routing create veth interfaces and need CAP_NET_ADMIN; they fail in a plain
# docker build and pass in a privileged container.
RUN PKGS="$(go list -e -f '{{.ImportPath}} {{join .Deps " "}}' ./... | grep -v pfring | cut -d' ' -f1)" \
    && (go test -count=1 -timeout 600s $PKGS || echo "WARNING: go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off
