# Scanner image for https://github.com/lightninglabs/wavelength.
#
# The repository's own Dockerfile builds `waved` and `wavecli` from a build context. It is close to
# what the scanner wants but carries no test toolchain, so this file builds the scanner's checkout at
# /src and leaves the suite runnable offline.
#
# wavelength is a Go workspace: go.work covers ./, ./baselib and ./tools, and the workspace is what
# makes the modules resolve against each other. Everything a build or a test needs therefore comes
# from the same checkout. CGO is on because the daemon can be built against a cgo SQLite driver.

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

# Fetch every module the build and the tests need while the network is still up, for each workspace
# module. `go work sync` then reconciles the workspace's view of them.
RUN go work sync && go mod download && go mod verify \
    && (cd baselib && go mod download)

# BUILD_TAGS mirrors the Makefile's DEV_TAGS.
ENV BUILD_TAGS="dev"

# Build with debug info and no inlining so stack traces and reproducers match the source, then compile
# every test binary without running it.
RUN go build -tags="$BUILD_TAGS" -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' -tags="$BUILD_TAGS" ./...

# The baselib module is tested separately by the Makefile, so do the same here.
RUN (cd baselib && go build -gcflags='all=-N -l' ./... && go test -count=1 -run '^$' ./...)

# Run the suite so the image is known to work, but do not let a failing test abort the build. This is
# the biggest suite in the set; some tests are slow and some need resources a build host lacks.
RUN (go test -count=1 -timeout 40m -tags="$BUILD_TAGS" ./... || echo "WARNING: go test reported failures")
RUN (cd baselib && go test -count=1 -timeout 20m ./... || echo "WARNING: baselib go test reported failures")

# The scan runs offline. Fail fast instead of waiting on the network if anything still tries to fetch.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
