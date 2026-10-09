# Ekubo MCP server: Cloudflare Worker in TypeScript, built and tested with Bun.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip python3 jq nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV BUN_INSTALL=/opt/bun PATH=/opt/bun/bin:$PATH
RUN curl -fsSL https://bun.sh/install | bash -s "bun-v1.3.14" && bun --version

COPY . /src
WORKDIR /src

RUN bun install --frozen-lockfile
RUN bun run build
RUN (timeout 900 bun run test || echo "WARNING: bun test reported failures or timed out")
