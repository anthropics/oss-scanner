# Scanner image for github.com/gofiber/contrib (main, the v3 modules). threat_model.md says how to exercise it.
FROM golang:1.27-bookworm

# redis-server lets the uptime module's Redis store run on loopback: its own integration test starts Redis through Docker,
# which a scan cannot do. Best effort, because nothing else needs it.
RUN (apt-get update && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*) \
    || echo "WARNING: redis-server was not installed"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# contrib is one Go module per directory under v3/ (24 of them; no go.work, no replace directives), so each step below
# runs once per module. Fetch and build everything while the network is up; the audit runs offline.
RUN set -e; for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; (cd "$m" && go mod download && go build ./...); \
    done

# Warm the build cache with every test binary, plain and -race. -vet=off: a vet finding must not fail the build.
RUN for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile"); \
      (cd "$m" && go test -vet=off -race -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile with -race"); \
    done

# Run every suite so the log shows the image works; a failing or hung test must not fail the build. testcontainers and
# uptime's TestNewRedisStoreIntegration start containers through Docker, so they fail here: that is expected.
RUN timeout 1200 sh -c 'for m in $(find . -name go.mod -not -path "./.git/*" -printf "%h\n" | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -race -count=1 -timeout 5m ./... || echo "WARNING: $m: go test reported failures"); \
    done' || echo "WARNING: the test run did not finish within 20 minutes"

# The audit is offline: no module proxy, no checksum database, no toolchain download.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local
