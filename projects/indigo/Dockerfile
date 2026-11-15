FROM node:22-bookworm AS node
FROM golang:1.26-bookworm

COPY --from=node /usr/local/ /usr/local/
COPY --from=node /opt/ /opt/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates build-essential git pkg-config python3 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/local/go/bin/go /usr/local/bin/go \
    && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt

ENV CGO_ENABLED=1 \
    GOTOOLCHAIN=local \
    GOFLAGS=-mod=readonly \
    GOBIN=/usr/local/bin

COPY . /src
WORKDIR /src

RUN go mod download

RUN go build -p 2 ./... \
    && go install -p 2 ./cmd/... \
    && go test -p 2 -run '^$' ./...

RUN cd /src/cmd/relay/relay-admin-ui \
    && yarn install --frozen-lockfile --non-interactive \
    && yarn build \
    && mkdir -p /src/public \
    && cp -a dist/. /src/public/

CMD ["bash"]
