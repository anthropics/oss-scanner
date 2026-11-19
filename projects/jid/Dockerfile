FROM golang:1.25-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Keep module sources and the compiler available for offline tests and fuzzing.
RUN go mod download && go mod verify
RUN go build -o /usr/local/bin/jid ./cmd/jid
RUN go test ./...

ENV GOPROXY=off GOSUMDB=off
