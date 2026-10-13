FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      git \
      libsecret-1-dev \
      pkg-config \
      python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . /src

# Install the JavaScript packages used by ADE's runtime, desktop, web client,
# relays, and shared SDKs.
RUN set -eu; \
    for package in \
      apps/ade-cli \
      apps/desktop \
      apps/web \
      apps/webhook-relay \
      apps/tunnel-relay \
      apps/push-relay \
      apps/account-directory \
      packages/sdk \
      packages/chat-ui; do \
      (cd "/src/$package" && npm ci); \
    done

# Build the Node-based products and workers. Swift/iOS targets need macOS and
# are not built in this Linux image.
RUN set -eux; \
    cd /src/apps/ade-cli && npm run build; \
    cd /src/apps/desktop && npm run build; \
    cd /src/apps/web && npm run build; \
    cd /src/apps/webhook-relay && npm run build; \
    cd /src/apps/account-directory && npm run build; \
    cd /src/packages/sdk && npm run build; \
    cd /src/packages/chat-ui && npm run build

# tools/check opens the final shell as root. Give the unprivileged node user
# write access to package directories so Vitest can create its config and cache
# files when permission-sensitive tests run as node.
RUN set -eu; \
    for package in \
      apps/ade-cli \
      apps/desktop \
      apps/web \
      apps/webhook-relay \
      apps/tunnel-relay \
      apps/push-relay \
      apps/account-directory \
      packages/sdk \
      packages/chat-ui; do \
      chown node:node "/src/$package" "/src/$package/node_modules"; \
    done
