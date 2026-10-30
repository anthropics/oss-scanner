FROM golang:1.27-bookworm AS go-toolchain

FROM node:24.21.0-bookworm
COPY --from=go-toolchain /usr/local/go /usr/local/go

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/root/go/bin:/usr/local/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    CGO_ENABLED=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PUPPETEER_SKIP_DOWNLOAD=true \
    CYPRESS_INSTALL_BINARY=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git jq sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN go mod download \
    && go install github.com/magefile/mage@latest

WORKDIR /src/frontend
RUN npm install -g corepack \
    && corepack enable \
    && pnpm install --frozen-lockfile \
    && pnpm run build

WORKDIR /src
# No -s -w (unlike mage build:build) to keep debug info.
RUN go build -tags osusergo -o /src/vikunja . \
    && ln -s /src/vikunja /usr/local/bin/vikunja

# Default test DB is in-memory sqlite, so no DB service needed.
RUN go test -short -p 1 -timeout 45m ./... \
    || echo "WARNING: go feature tests failed"
RUN go test -p 1 -timeout 45m ./pkg/webtests \
    || echo "WARNING: go web tests failed"
RUN cd frontend && (pnpm exec vitest run --dir ./src || echo "WARNING: frontend unit tests failed")

ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
