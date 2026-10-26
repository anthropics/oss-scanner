# syntax=docker/dockerfile:1
# Scanner-only build environment for Anthropic's OSS Scanner.
# ITCake itself is deployed without Docker; this file exists only so the
# scanner can build the project and run its tests in an offline sandbox.

FROM golang:1.27.3-bookworm AS go

FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_OPTIONS=--max-old-space-size=4096 \
    PUPPETEER_CACHE_DIR=/opt/puppeteer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential pkg-config \
      curl openssl procps iputils-ping dnsutils jq sqlite3 unzip file \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
      libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
      libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 \
      libcairo2 libasound2 libxshmfence1 libdbus-1-3 libexpat1 \
      libfontconfig1 libglib2.0-0 libgtk-3-0 libx11-6 libx11-xcb1 \
      libxcb1 libxcursor1 libxext6 libxi6 libxrender1 libxss1 libxtst6 \
      fonts-liberation fonts-dejavu-core lsb-release wget xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=go /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0 \
    GOFLAGS=-buildvcs=false

# The scanner supplies the ITCake checkout as the build context.
# Keep the entire checkout in the image.
COPY . /src
WORKDIR /src

# Node dependencies, browser for PDF rendering, and production build.
RUN npm ci
RUN npx puppeteer browsers install chrome
RUN npm run build

# Go agent dependencies and build.
RUN cd agent \
    && go mod download \
    && go build ./...

# Build the cross-platform agent binaries so the app's download endpoint
# can be exercised (they are written to data/agent-binaries).
RUN npm run build:agent:all

# Fail the image if Chromium cannot launch; PDF generation depends on it.
RUN node --input-type=module -e "import puppeteer from 'puppeteer'; const b = await puppeteer.launch({ args: ['--no-sandbox'] }); console.log('Chrome', await b.version()); await b.close();"

# Baseline tests. Keep the image usable even if a stock test fails.
RUN (npm test -- --run tests/unit/ || echo "WARNING: unit tests reported failures") \
 && (cd agent && go test ./... || echo "WARNING: Go tests reported failures")

# Make the offline contract explicit for the scanner.
ENV GOPROXY=off \
    GOSUMDB=off
