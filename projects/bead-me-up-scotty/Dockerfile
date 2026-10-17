# OSS Scanner build of Bead Me Up, Scotty (main).
#
# A Next.js 16 app that serves a local web UI and shells out to the `bd`
# (beads) CLI. The checkout is in /src, built for production.
#
# Exercise it (no network needed):
#   cd /src && BEADS_DEMO=1 npx next start -p 3917 -H 127.0.0.1 &
#   SCOTTY_TEST_URL=http://127.0.0.1:3917 node scripts/test-request-guard.mjs
# Every scripts/test-*.mjs regression script takes SCOTTY_TEST_URL; some expect a
# server started with SCOTTY_READ_ONLY=1 (see the script headers). Real bd data:
#   git init /tmp/p && cd /tmp/p && bd init --prefix t, then register /tmp/p via
#   POST /api/projects {"path":"/tmp/p"}.
FROM node:26.4.0-slim

ARG BD_VERSION=1.3.1
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive \
    NEXT_TELEMETRY_DISABLED=1 \
    POSTHOG_KEY= \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

# bd, the CLI the app runs for every read and write.
RUN arch="${TARGETARCH:-$(dpkg --print-architecture)}" \
    && curl -fsSL "https://github.com/gastownhall/beads/releases/download/v${BD_VERSION}/beads_${BD_VERSION}_linux_${arch}.tar.gz" \
       | tar -xz -C /usr/local/bin bd \
    && bd --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
RUN npm ci --no-audit --no-fund \
    && npx playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
RUN npm run build

RUN git config --global user.name "OSS Scanner" && git config --global user.email "scanner@localhost"
# Cheap checks; a failure here must not abort the image.
RUN (npx tsc --noEmit && npm run lint) || echo "WARNING: typecheck or lint reported problems"
