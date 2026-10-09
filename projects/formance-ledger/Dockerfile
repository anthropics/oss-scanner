FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

# Keep PostgreSQL available for local API reproducers without external services.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq python3 postgresql postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

# The scanner expects the full checkout and build tools to remain at /src.
COPY . /src
WORKDIR /src

# Fetch dependencies while networking is available, including the local client module.
RUN go mod download && cd pkg/client && go mod download
RUN go build -o /usr/local/bin/ledger .

# The service's unit tests run without Docker or production credentials.
# test/migrations and tests behind the it tag require Docker-managed services.
RUN go test -count=1 -timeout=10m . ./cmd/... ./internal/... ./pkg/... \
    && cd pkg/client && go test -count=1 -timeout=5m ./...
