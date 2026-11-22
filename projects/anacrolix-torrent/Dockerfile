# Scanner image for https://github.com/anacrolix/torrent.
#
# The module is a BitTorrent client library in Go. The go.work file also pulls in the Go bindings of
# the possum storage backend from the storage/possum/lib submodule, whose Rust library is linked via cgo
# (see the justfile), so the submodule and a Rust toolchain are needed to build and test everything.

FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local \
    PATH=/root/.cargo/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config curl fuse3 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner clones only the top-level repository; fetch the possum submodule.
RUN git -c credential.helper= submodule update --init --recursive

# Build the possum Rust library (what `just build-possum` does) and fetch everything offline use needs.
RUN cd storage/possum/lib && cargo fetch && cargo build --lib
ENV CGO_LDFLAGS=-L/src/storage/possum/lib/target/debug

RUN go mod download && go mod verify \
    && (cd storage/possum/lib/go && go mod download)

# Build with debug info and no inlining, then compile every test binary (with and without -race)
# without running it, so the build and test caches are warm for the offline audit.
RUN go build -gcflags='all=-N -l' ./... \
    && go test -count=1 -run '^$' ./... \
    && go test -race -count=1 -run '^$' ./...

# Run the short suite so the image is known to work (what `just test-short` runs), but do not let a
# failing test abort the build. FUSE-dependent tests may not work inside the container.
RUN go test -race -short ./... || echo "WARNING: go test reported failures"
