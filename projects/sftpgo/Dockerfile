FROM docker.io/library/golang:1.27-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git procps \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

ENV GO_TAGS=nopgxregisterdefaulttypes,disable_grpc_modules

# Root module plus the plugins used by the test suite.
RUN go mod download \
    && (cd tests/eventsearcher && go mod download) \
    && (cd tests/ipfilter && go mod download)

RUN go build -trimpath -tags "$GO_TAGS" \
      -ldflags "-X github.com/drakkan/sftpgo/v2/internal/version.commit=$(git describe --always --abbrev=8 --dirty) -X github.com/drakkan/sftpgo/v2/internal/version.date=$(date -u +%FT%TZ)" \
      -o sftpgo \
    && ./sftpgo --version \
    && ln -s /src/sftpgo /usr/local/bin/sftpgo

RUN go test -tags "$GO_TAGS" -count=1 -exec /bin/true ./...

ENV GOPROXY=off \
    GOSUMDB=off \
    GOTOOLCHAIN=local

CMD ["bash"]
