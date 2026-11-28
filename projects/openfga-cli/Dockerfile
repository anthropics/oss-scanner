# Scanner image for https://github.com/openfga/cli (main).
#
# The audit runs offline, so this build fetches every Go module, builds the `fga` binary and the tests (with and
# without -race), and installs an OpenFGA server so `fga` has something to talk to. threat_model.md, next to this
# file, says how to use each of them.

# go.mod sets `go 1.26.0` and `toolchain go1.27.3`; the image must carry a toolchain at least that new because the
# build below uses GOTOOLCHAIN=local.
FROM golang:1.27-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1

# curl and jq for the server's HTTP API; sqlite3 to inspect the SQLite file used by the server.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# A server for `fga` to call, at the version the CLI itself builds against (go.mod). Installed while the network is up.
RUN OPENFGA_VERSION="$(go list -m -f '{{.Version}}' github.com/openfga/openfga)" \
    && GOBIN=/usr/local/bin go install "github.com/openfga/openfga/cmd/openfga@${OPENFGA_VERSION}" \
    && mkdir -p /var/lib/openfga \
    && openfga migrate --datastore-engine sqlite --datastore-uri 'file:/var/lib/openfga/openfga.db'

# From here on use the toolchain in the image, never a downloaded one.
ENV GOTOOLCHAIN=local

# The CLI, and every package's tests compiled with and without the race detector so the build cache is warm offline.
# Mocks are checked in, so `make generate-mocks` is not needed. A step that fails fails the build, and primary_contact
# gets the log.
RUN go mod download \
    && go build -o /usr/local/bin/fga ./cmd/fga \
    && go test -run '^$' ./... \
    && go test -race -run '^$' ./...

# The unit tests, which need no server, so the log shows the image works without letting a failure abort the build.
RUN (timeout 1200 go test -count=1 -timeout 15m ./... \
       || echo "WARNING: go test reported failures")

# Everything is fetched. From here on the go command must not try to reach a proxy.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
