# Builds Wings from the checkout at /src and keeps the Go module cache, so it builds and tests offline.
FROM docker.io/library/golang:1.27-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential procps \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# If go.mod asks for a newer Go than this image has, the toolchain is downloaded here and cached.
RUN go mod download

RUN go build -o /usr/local/bin/wings -v wings.go && wings version || true
RUN go build ./... && go vet ./... || echo "WARNING: go vet reported problems"

# Baseline tests; a failing test must not abort the build.
RUN go test -short -timeout 20m ./... || echo "WARNING: baseline Go tests reported failures"

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod

CMD ["bash"]
