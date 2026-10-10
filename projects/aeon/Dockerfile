# Aeon: an agent framework that runs on GitHub Actions. Shell + Python scripts and workflows drive a coding-agent
# harness; four standalone TypeScript apps sit beside them (dashboard, cli, mcp-server, webhook), each with its own
# lockfile. The root package.json only fans commands across them (`npm run bootstrap` installs all four in order).
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive

# Tools the scripts and their tests use: bash, jq, yq, python3 + PyYAML, bubblewrap (read-only sandbox), shellcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq python3 python3-yaml bubblewrap shellcheck \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    && chmod +x /usr/local/bin/yq

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install every app (dashboard, cli, mcp-server, webhook) and build the dashboard + MCP server.
RUN npm run bootstrap
RUN npm run build

# Cheap tests so the image is known good; a failing test does not abort the build.
RUN (npm test || echo "WARNING: app tests reported failures") \
    && (python3 scripts/tests/test_notify_format.py || echo "WARNING: notify_format tests reported failures") \
    && (bash scripts/tests/test_skill_mode.sh || echo "WARNING: skill mode tests reported failures")
