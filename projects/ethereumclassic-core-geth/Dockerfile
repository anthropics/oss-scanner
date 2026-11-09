# Core-Geth, an Ethereum Classic execution client: the build image for Anthropic's OSS Scanner.
#
# This file sits next to project.yaml. The scanner builds it with a clone of
# https://github.com/ethereumclassic/core-geth (branch main) as the build context. The network is
# available while this file builds and is removed afterwards, so everything the build and the
# tests need is fetched in this file.
#
# The Go release matches the `# version:golang` line of build/checksums.txt on main, the toolchain
# the project's release archives are built with.
FROM golang:1.26.8-trixie@sha256:aae9c439b447d24c93ee483408992857cf39a3fb6ab7fe53affc65d834891fa8

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git python3 \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# The repository's root .dockerignore keeps test files and the fixture submodules out of its own
# images. Restore any tracked file the build context left out, so this image holds the tests
# whichever ignore file applied.
RUN git checkout -- .

# The three fixture submodules, at the commits the checkout records, from the URLs in .gitmodules.
RUN git submodule update --init --recursive --depth 1

# Every module the build and the tests use.
RUN go mod download

# Every command under cmd/, as the project's release builds make them: build/ci.go install, with
# the release build tags. The binaries keep their debug information and go to build/bin.
RUN make all

# Compile the tests of every package, so they run offline. -run '^$' selects none of them.
RUN go test -count=1 -run '^$' ./...

# A short test pass over consensus, chain configuration, block types and the wire protocols. It
# runs through build/ci.go, which also fetches the execution-spec-tests fixtures that `make test`
# reads, checked against build/checksums.txt. A failing test is reported and does not stop the
# build; missing fixtures do.
RUN go run build/ci.go test -short ./consensus/... ./params/... ./core/types/... ./eth/protocols/... \
      || echo "WARNING: the short test pass reported failures"; \
    test -d tests/spec-tests \
      || { echo "ERROR: build/ci.go did not fetch the execution-spec-tests fixtures"; exit 1; }

# The scan runs offline: refuse module downloads instead of waiting for a network.
ENV GOPROXY=off
