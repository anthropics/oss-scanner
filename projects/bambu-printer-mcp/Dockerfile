FROM node:24-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies an anonymous checkout, never a maintainer's local config.
COPY . /src
WORKDIR /src
ENV PRINTER_HOST=127.0.0.1 \
    BAMBU_SERIAL= \
    BAMBU_TOKEN= \
    BAMBU_MODEL= \
    BAMBU_REQUIRE_CONFIRMATION=1 \
    MCP_TRANSPORT=stdio \
    npm_config_audit=false \
    npm_config_fund=false

# Keep npm's cache: the desktop packaging test needs its prefetched dependencies.
# Full tests also exercise clean npm installs while build networking is available.
RUN npm ci && npm run build
RUN mkdir -p /opt/oss-scanner-validation \
    && if npm test > /opt/oss-scanner-validation/build-tests.log 2>&1; then \
         echo 0 > /opt/oss-scanner-validation/build-tests.exit; \
       else \
         echo $? > /opt/oss-scanner-validation/build-tests.exit; \
         cat /opt/oss-scanner-validation/build-tests.log; \
         echo 'WARNING: tests failed; inspect build-tests.log before relying on results'; \
       fi

# Only the fresh npm-install test creates an intentionally empty private cache.
# It runs above, but cannot run offline. All other test files remain enabled.
ENV npm_config_offline=true
RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    'cd /src' \
    'npm run build' \
    "node --test --test-skip-pattern='^published tarball patches the resolved dependency in local, global, and npm-exec installs$' tests/*.test.mjs tests/**/*.test.mjs" \
    > /usr/local/bin/test-offline \
    && chmod +x /usr/local/bin/test-offline

CMD ["bash"]
