# MCP TypeScript SDK, built and tested the way its CI (.github/workflows/main.yml) does: pnpm install from the committed
# lockfile, build every package, then vitest in each workspace. node:24-bookworm includes git, python3 and a C++
# toolchain, which better-sqlite3 (a development dependency) needs if it has no prebuilt binary.
FROM node:24-bookworm

ENV CI=true

# The version in package.json's "packageManager".
RUN npm install -g pnpm@10.26.1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile
RUN pnpm run build:all

# Every suite except the e2e one, as in CI. The Cloudflare Workers test runs `npm install`: running it here, with a
# network, fills the npm cache that it uses later. A failing test must not abort the image build.
RUN timeout 1200 pnpm -r --no-bail --filter '!@modelcontextprotocol/test-e2e' test || echo "WARNING: tests reported failures"
