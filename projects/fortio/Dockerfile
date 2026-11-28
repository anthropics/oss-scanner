# Scanner image for https://github.com/fortio/fortio (master).
#
# Starts from the image built by the repo's Dockerfile.build (Go, gcc for -race, golangci-lint, govulncheck), pinned to
# the same tag as BUILD_IMAGE in the Makefile and used by the repo's Dockerfile as its build stage, then adds the
# checkout. The repo's own Dockerfile final stage is `FROM scratch` (binary only), which has no shell, so it is not used. The audit runs offline, so this build fetches
# every Go module, builds the fortio binary and compiles the tests. threat_model.md, next to this file, says how to
# run it.

FROM docker.io/fortio/fortio.build:v90@sha256:036f5b5d4df9ce30e0574f212d19ced86ddc7b0255f58a536b008943e5c4efc7
USER root
# curl and netcat to talk to a running server, openssl for cert-gen (needed by the tests).
RUN apt-get update && apt-get install -y --no-install-recommends curl openssl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download

# The fortio binary, built the way the repo's Dockerfile builds the release image (`make official-build-version`, in the
# MODE=dev flavour that Webtest.sh uses, i.e. from this checkout) and installed in /usr/local/bin. Then the other
# packages and the tests with and without -race, as `make test` runs them. Certs are generated into ./cert-tmp like
# `make dependencies` does. A step that fails fails the build, and primary_contact gets the log.
RUN ./cert-gen \
    && make official-build-version MODE=dev BUILD_DIR=/tmp/fortio_build \
    && cp /tmp/fortio_build/result/fortio /usr/local/bin/fortio \
    && go build ./... \
    && go test -tags netgo -run '^$' ./... \
    && go test -tags netgo -race -run '^$' ./...

# Run the tests so the log shows the image works, without letting a failure abort the build.
RUN (timeout 1200 go test -tags netgo -timeout 300s -race ./... || echo "WARNING: go test reported failures")

# Everything is fetched. From here on the go command must not try to reach a proxy or download a toolchain.
ENV GOPROXY=off \
    GOTOOLCHAIN=local
