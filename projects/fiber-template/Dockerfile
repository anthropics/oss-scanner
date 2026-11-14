# Scanner image for github.com/gofiber/template (master: the core module and nine engines). threat_model.md says how to exercise it.
FROM golang:1.27-bookworm

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# template is ten Go modules: the core at the root and one engine per directory. There is no go.work; every engine
# builds against the checkout's core through a replace directive, so each step below runs once per module.
# Fetch and build everything while the network is up; the audit runs offline.
RUN set -e; for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; (cd "$m" && go mod download && go build ./...); \
    done

# Warm the build cache with every test binary, plain and -race. -vet=off: a vet finding must not fail the build.
RUN for m in $(find . -name go.mod -not -path './.git/*' -printf '%h\n' | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile"); \
      (cd "$m" && go test -vet=off -race -run '^$' ./... || echo "WARNING: $m: some test binaries do not compile with -race"); \
    done

# Run every suite so the log shows the image works; a failing or hung test must not fail the build.
RUN timeout 900 sh -c 'for m in $(find . -name go.mod -not -path "./.git/*" -printf "%h\n" | sort); do \
      echo "=== $(date +%T) $m"; \
      (cd "$m" && go test -vet=off -race -count=1 -timeout 5m ./... || echo "WARNING: $m: go test reported failures"); \
    done' || echo "WARNING: the test run did not finish within 15 minutes"

# The audit is offline: no module proxy, no checksum database, no toolchain download.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local
