# Scanner image for github.com/gofiber/schema (main). threat_model.md says how to exercise it.
FROM golang:1.27-bookworm

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch and build everything while the network is up; the audit runs offline.
RUN go mod download
RUN go build ./...

# Warm the build cache with the test binary, plain and -race. -vet=off: a vet finding must not fail the build.
RUN (go test -vet=off -run '^$' ./... || echo "WARNING: the test binary does not compile") \
    && (go test -vet=off -race -run '^$' ./... || echo "WARNING: the test binary does not compile with -race")

# Run the suite so the log shows the image works; a failing or hung test must not fail the build.
RUN (timeout 900 go test -vet=off -race -count=1 -timeout 10m ./... || echo "WARNING: go test reported failures")

# The audit is offline: no module proxy, no checksum database, no toolchain download.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local
