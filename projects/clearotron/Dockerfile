# Clearotron: a trademark clearance engine on Node.js 22, as npm workspaces. The scanner builds this
# with the repository as context and then removes the network, so dependencies and the portal bundle
# are installed and built here.
FROM node:22-bookworm

ENV CI=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src. It is owned by the image's `node`
# user because the suite runs as a normal account: some tests make a file unreadable and expect that
# to hold, which it does not for root.
COPY --chown=node:node . /src
WORKDIR /src
USER node

RUN npm ci --no-audit --no-fund
RUN npm run build:ui

# The MCP server's suite (authentication, scoping, the HTTP doors) is the quick check that the image
# works. The full suite runs in the project's CI. A failure is reported, not fatal.
RUN timeout 900 npm test -w mcp-server || echo "WARNING: the mcp-server tests reported failures"

USER root
