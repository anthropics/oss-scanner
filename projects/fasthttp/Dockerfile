FROM golang:1.27-bookworm

ENV GOTOOLCHAIN=local

# The scanner expects the complete checkout at /src.
COPY . /src
WORKDIR /src

# Download dependencies and warm both build caches while networking is available.
RUN go mod download && go mod verify
RUN go build ./...
RUN go test -run '^$' ./...
RUN go test -race -run '^$' ./...

# Exercise the image, but leave it available for investigation if tests fail.
RUN (timeout 900 go test -count=1 -timeout=10m ./... || echo "WARNING: go test reported failures")
RUN (timeout 900 go test -race -count=1 -timeout=10m ./... || echo "WARNING: go test -race reported failures")

# Scanning and subsequent test runs must work without module or toolchain downloads.
ENV GOPROXY=off \
    GOSUMDB=off
