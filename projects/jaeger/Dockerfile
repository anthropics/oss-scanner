# Jaeger (Go). Mirrors the unit-test and build steps in .github/workflows (make test / make build-binaries).
FROM golang:1.27-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=auto \
    CGO_ENABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# idl/ and jaeger-ui/ are git submodules; fetch them now if the checkout carries .git (network is up only here).
RUN git config --global --add safe.directory /src \
    && (git submodule update --init --recursive --depth 1 || echo "WARNING: submodule fetch skipped")

RUN go mod download && go mod verify
# Main binary (embeds a placeholder UI when jaeger-ui assets are not built) plus every package.
RUN go build -o /usr/local/bin/jaeger ./cmd/jaeger && go build ./...
# Pre-build test binaries/deps so tests run offline later.
RUN go test -count=1 -short -timeout 20m ./... || echo "WARNING: go test reported failures"
