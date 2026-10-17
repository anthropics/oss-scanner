FROM golang:1.27.2-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN for i in 1 2 3; do go mod download && break; sleep 10; done && go mod download

RUN go build ./...

# Compile every test binary so offline runs only relink.
RUN go test -run '^$' ./...

RUN (go test ./... || echo "WARNING: go test reported failures") \
    && git status --short

ENV GOPROXY=off \
    GOFLAGS=-mod=readonly
