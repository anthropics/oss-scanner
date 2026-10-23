# Dockhand: a SvelteKit/Node.js web app that manages Docker hosts, plus a small Go
# collector. Built here the way the release image builds it, with the dev
# dependencies and toolchains kept so the tests can run offline.
FROM node:24.18.1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl jq python3 make g++ unzip \
    && rm -rf /var/lib/apt/lists/*

# Go for the collector (collector/go.mod), bun for the unit tests (tests/).
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://go.dev/dl/go1.26.9.linux-${ARCH}.tar.gz" | tar -C /usr/local -xz \
    && npm install -g bun@1.3.10
ENV PATH=/usr/local/go/bin:/root/go/bin:$PATH

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Same steps as the release Dockerfile: install without lifecycle scripts, then compile
# the two native addons, then build. The build needs a larger heap than Node's default.
RUN npm ci --ignore-scripts \
    && npm rebuild better-sqlite3 argon2 \
    && NODE_OPTIONS=--max-old-space-size=6144 npm run build

RUN cd collector && go mod download && go build -o /src/bin/collection-worker .

# Unit tests; a failure is reported but does not fail the image.
RUN bun test tests/ || echo "WARNING: unit tests reported failures"
