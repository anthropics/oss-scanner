# OpenNHP build for the Anthropic OSS Scanner.
#
# The scanner builds this image with the opennhp repository as the build
# context (COPY . /src). Network access is available during this build and
# is removed for the offline analysis that follows, so every dependency the
# scanner might need is fetched here.
FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOFLAGS=-mod=mod

# git for version stamping; build-essential provides the C toolchain cgo
# needs (nhp-serverd loads its auth plugins via plugin.Open, which requires
# cgo).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# OpenNHP is split into two Go modules joined by a local replace directive —
# nhp/ (the core protocol library: Noise handshake, packet parsing, crypto)
# and endpoints/ (the daemons: server, ac, relay, agent, db) — plus demoapp/
# (an example web backend). Pre-fetch every module's dependencies while the
# network is still up.
RUN cd /src/nhp       && go mod download all \
 && cd /src/endpoints && go mod download all \
 && cd /src/demoapp   && go mod download all

# Build both core modules. -mod=mod (via GOFLAGS) tolerates minor go.mod
# drift; symbols are kept (no -s -w) so reported findings can carry useful
# reproducers.
RUN cd /src/nhp       && go build ./... \
 && cd /src/endpoints && go build ./...

# Build the daemons as unstripped binaries where an agent can exercise them.
RUN mkdir -p /out \
 && cd /src/endpoints \
 && go build -o /out/nhp-serverd ./server/main/main.go \
 && go build -o /out/nhp-acd     ./ac/main/main.go \
 && go build -o /out/nhp-relayd  ./relay/main/main.go \
 && go build -o /out/nhp-agentd  ./agent/main/main.go \
 && go build -o /out/nhp-db      ./db/main/main.go

# demoapp Go backend. The embedded SPA requires Node (the `webdist` build
# tag); without it the server builds and runs, reporting "UI not built".
# Non-fatal so a demoapp issue can't block scanning the core protocol.
RUN cd /src/demoapp && go build -o /out/demoapp . \
    || echo "WARNING: demoapp build failed (non-fatal)"

# Run the test suites so the image is known-good, but never let a flaky or
# environment-dependent test abort the build (some server tests expect a
# mounted bpffs / privileged host).
RUN cd /src/nhp && (go test -count=1 ./... \
      || echo "WARNING: nhp tests reported failures")
RUN cd /src/endpoints && (go test -count=1 ./... \
      || echo "WARNING: endpoints tests reported failures")
