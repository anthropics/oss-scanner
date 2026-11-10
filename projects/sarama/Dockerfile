# syntax=docker/dockerfile:1
#
# Compile-only check for Sarama: builds every package, tool and example,
# and compiles and links every test binary (with and without the
# "functional" build tag) without running any tests.
#
FROM golang:1

ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOFLAGS=-mod=readonly

WORKDIR /src

RUN --mount=type=bind,target=. \
    --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    set -eu; \
    for mod in $(find . -name go.mod -not -path './.git/*' -exec dirname {} \; | sort); do \
      echo "==> ${mod}"; \
      ( cd "${mod}" \
        && go build -o /out/ ./... \
        && go test -exec /bin/true -count=1 ./... \
        && go test -exec /bin/true -count=1 -tags functional ./... \
      ); \
    done
