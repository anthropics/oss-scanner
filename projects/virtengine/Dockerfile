# Builds the `virtengine` binary (CometBFT/Cosmos SDK node + CLI) from the checkout at /src.
FROM golang:1.26.8-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential pkg-config git make libusb-1.0-0-dev libhidapi-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module now; the audit runs without network access.
RUN go mod download

# Build with debug info (no -s/-w stripping) so findings can be reproduced under a debugger.
RUN go build -gcflags="all=-N -l" -o /src/bin/ ./cmd/...

# Warm the build/test cache for the security suite, but do not fail the image on test failures.
RUN (go test -tags=security -count=1 ./tests/security/... || echo "WARNING: security tests reported failures")
