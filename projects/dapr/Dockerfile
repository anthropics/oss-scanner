# Scanner image for https://github.com/dapr/dapr (master).
# Fetches every Go module the runtime, unit tests and integration tests need, builds the control plane
# and daprd, and warms the build cache so tests and reproducers rebuild quickly offline.
# If go.mod asks for a newer Go than this image has, the toolchain is downloaded here and stays in the
# module cache for offline use.
FROM docker.io/library/golang:1.26-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make procps \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Root module plus the integration test helper modules (each has its own go.mod).
RUN go mod download \
    && for d in tests/integration/framework/binary/helpers/*/; do (cd "$d" && go mod download); done

# The shipped binaries, built as the release does.
RUN for name in daprd placement sentry operator injector scheduler; do \
      CGO_ENABLED=0 go build -tags=allcomponents -o "/usr/local/bin/$name" "./cmd/$name" || exit 1; \
    done \
    && daprd --version

# The integration framework compiles daprd and the control plane with its own build tags and generates the
# CRDs before any test runs. A focus that matches nothing does just that, which warms the build cache.
# DAPR_INTEGRATION_*_PATH stay unset on purpose, so every run rebuilds from the (possibly patched) source.
RUN go test -tags=integration -count=1 -timeout=60m ./tests/integration -focus='^$'

# Smoke test: health endpoints of daprd and each control plane service. Failures must not abort the build.
RUN go test -tags=integration -count=1 -timeout=10m ./tests/integration -focus='^healthz/' \
    || echo 'WARNING: integration smoke tests reported failures'

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
