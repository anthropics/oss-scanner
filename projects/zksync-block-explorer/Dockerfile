# ZKsync block explorer: an npm workspaces + lerna monorepo (NestJS api, worker, data-fetcher; Vue app) on Node 22.
# Mirrors .github/workflows/validate-pr.yml: npm ci, unit tests, build. The unit tests are self-contained -- CI runs
# them on a bare runner with no database.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 build-essential xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Node 22 with bundled npm, as CI's setup-node resolves.
RUN arch="$(dpkg --print-architecture | sed 's/amd64/x64/')" \
    && curl -fsSL --retry 5 --retry-all-errors "https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-${arch}.tar.xz" \
       -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && npm cache clean --force

COPY . /src
WORKDIR /src

# Retries and a modest socket count keep the install alive on builders with flaky NAT to the registry.
RUN npm ci --fetch-retries=5 --fetch-retry-mintimeout=5000 --fetch-retry-maxtimeout=120000 --maxsockets=6

RUN npm run build

# Nothing below this line, or in the scan, may reach the network.

# Smoke-test the suites as CI runs them. Test failures do not fail the build.
RUN (timeout 2400 npm run test:ci || echo "WARNING: npm run test:ci reported failures or timed out") \
    && rm -f packages/*/junit.xml

# Start the scan from a tree identical to HEAD, so a patch carries only its own changes.
RUN git checkout -- .
