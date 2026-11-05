# Scanner image for github.com/gofiber/storage (main). threat_model.md says how to exercise it.
FROM golang:1.27-bookworm

# Local servers for the drivers whose own tests start a container through Docker, which a scan cannot do. They are
# installed but not started (threat_model.md has the commands). Best effort and one package at a time, because nothing
# else needs them and one missing package must not drop the rest.
RUN apt-get update \
    && for p in redis-server memcached mariadb-server postgresql; do \
         DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$p" \
           || echo "WARNING: $p was not installed"; \
       done; \
    rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# storage is one Go module per directory (36 of them, the root and two test helpers included; no go.work, no replace
# directives), so each step below runs once per module. Fetch and build everything while the network is up; the audit
# runs offline.
RUN set -e; for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; (cd "$m" && go mod download && go build ./...); \
    done

# Warm the build cache with every test binary, plain and -race. -vet=off: a vet finding must not fail the build.
RUN for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile"); \
      (cd "$m" && go test -vet=off -race -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile with -race"); \
    done

# Run every suite so the log shows the image works; a failing or hung test must not fail the build. Most drivers' tests
# start their database through testcontainers, which needs a Docker daemon, so they fail at once here: that is expected.
# The embedded stores (memory, badger, bbolt, leveldb, pebble, ristretto, sqlite3, mockstorage) run in full.
RUN timeout 1500 sh -c 'for m in $(find . -name go.mod -not -path "./.git/*" -printf "%h\n" | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -race -count=1 -timeout 5m ./... || echo "WARNING: $m: go test reported failures"); \
    done' || echo "WARNING: the test run did not finish within 25 minutes"

# The audit is offline: no module proxy, no checksum database, no toolchain download.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local
