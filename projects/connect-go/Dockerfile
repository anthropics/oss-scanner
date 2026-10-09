# Scanner image for https://github.com/connectrpc/connect-go (main, which is v2: connectrpc.com/connect/v2).
#
# The audit runs offline, so this build fetches every module the repository's four Go modules depend on, builds the
# ConnectRPC conformance runner and the reference client and server, and compiles the library, its tests and the
# example server. threat_model.md, next to this file, says how to run each of them.

# The newest Go release, which is what the repository's CI lints and tests with. The image has git and gcc, which the
# race detector needs.
FROM golang:1.27-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# curl to speak the Connect protocol to a running server. Packages are fetched over HTTPS.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every module that the library, the example, the conformance harness and the migration tool depend on.
RUN go mod download \
    && (cd internal/example && go mod download) \
    && (cd internal/conformance && go mod download) \
    && (cd cmd/connect-go-v2-migrate && go mod download)

# The library and its tests (with and without -race, as `make shorttest` and `make slowtest` run them), the example
# server and client, and the conformance runner with the reference client and server, as
# internal/conformance/runconformance.sh builds them. A step that fails fails the build, and primary_contact gets the log.
RUN go build ./... \
    && go test -run '^$' ./... \
    && go test -race -run '^$' ./... \
    && (cd cmd/connect-go-v2-migrate && go build ./... && go test -run '^$' ./...) \
    && mkdir -p .tmp/bin \
    && (cd internal/example && go build -o ../../.tmp/bin/example-server ./server \
          && go build -o ../../.tmp/bin/example-client ./client) \
    && (cd internal/conformance \
          && go build -o ../../.tmp/bin/connectconformance connectrpc.com/conformance/cmd/connectconformance \
          && go build -o ../../.tmp/bin/referenceclient ./cmd/referenceclient \
          && go build -o ../../.tmp/bin/referenceserver ./cmd/referenceserver)

# Run the short tests and the server conformance suite so the log shows the image works, without letting a failure
# abort the build.
RUN (timeout 1200 go test -race -short ./... || echo "WARNING: go test reported failures") \
    && (cd internal/conformance && timeout 900 ../../.tmp/bin/connectconformance --mode server --conf config.yaml \
          -- ../../.tmp/bin/referenceserver || echo "WARNING: the conformance runner reported failures")

# Everything is fetched. From here on the go command must not try to reach a proxy or download a toolchain.
ENV GOPROXY=off \
    GOTOOLCHAIN=local
