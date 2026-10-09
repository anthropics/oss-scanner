# OSS Scanner builds this file using the Nezha repository as build context.
# This is a scan image, not Nezha's production runtime image.
FROM golang:1.26.6-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Make source, generated files, dependencies and a built Dashboard available offline.
RUN go mod download
RUN go install github.com/swaggo/swag/cmd/swag@v1.16.6
RUN mkdir -p cmd/dashboard/user-dist cmd/dashboard/admin-dist /src/build \
    && touch cmd/dashboard/user-dist/a cmd/dashboard/admin-dist/a \
    && /go/bin/swag init --pd -d cmd/dashboard -g main.go -o cmd/dashboard/docs \
    && go build -mod=readonly -o /src/build/nezha-dashboard ./cmd/dashboard

# Project tests can be run by the offline auditing agent with: go test -mod=readonly ./...
