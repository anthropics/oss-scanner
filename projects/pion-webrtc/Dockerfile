FROM golang:1.27-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV GOTOOLCHAIN=local
WORKDIR /src
COPY . /src
RUN go mod download && go mod verify
RUN go build ./...
RUN go test -count=1 -timeout=10m ./...
