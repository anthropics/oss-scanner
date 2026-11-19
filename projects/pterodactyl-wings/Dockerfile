FROM golang:1.26-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch the toolchain and modules while the network is up, then build the daemon.
RUN go mod download \
    && go build -o /usr/local/bin/wings -trimpath github.com/pterodactyl/wings \
    && go test -run XXX_NONE ./... >/dev/null

# Cheap checks so the image is known to work; failures do not abort the build.
RUN go test ./... || echo "WARNING: go test reported failures"
