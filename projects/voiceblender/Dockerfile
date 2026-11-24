FROM golang:1.26-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# go.mod pins a toolchain; resolve it now so later go commands work offline.
RUN go version && go mod download && go mod verify
RUN go build ./... \
    && go build -o /usr/local/bin/voiceblender ./cmd/voiceblender

# Compile the integration tests too, so they can be built and run offline.
RUN go vet -tags integration ./tests/integration/

RUN go test -count=1 -timeout=15m ./internal/... || echo "WARNING: unit tests reported failures"
