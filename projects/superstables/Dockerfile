FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    npm_config_audit=false \
    npm_config_fund=false
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies the public client checkout as the build context.
COPY --chown=node:node . /src
WORKDIR /src
USER node
ENV HOME=/home/node
# Keep development dependencies so agents can rebuild and run the existing suite offline.
# npm ci runs prepare, which builds the client and bundled budget rail scripts.
RUN npm ci --include=dev \
    && npm run typecheck \
    && npm run build
# Run as an ordinary user so filesystem-permission tests exercise real denial.
# Live seller/RPC tests are opt-in and excluded by the default test configuration.
RUN npm test
