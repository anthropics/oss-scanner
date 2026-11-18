# Builds kaniko's executor and warmer with debug info and warms the Go build cache for the unit tests.
# Dependencies are vendored, so nothing beyond the base image is fetched.
# Keep the Go version in sync with deploy/Dockerfile.
FROM golang:1.27.4

ENV CGO_ENABLED=0 \
    KANIKO_DIR=/kaniko

COPY . /src
WORKDIR /src

RUN go build -o out/executor ./cmd/executor \
    && go build -o out/warmer ./cmd/warmer

# The unit tests need /kaniko. A failing test does not fail the image.
RUN mkdir -p /kaniko \
    && (go test -timeout 300s $(go list ./... | grep -v -e /integration -e /golden) \
        || echo "WARNING: go test reported failures")
