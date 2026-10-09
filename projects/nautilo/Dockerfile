# syntax=docker/dockerfile:1
# Contributor runtime pins are declared in Nautilo's root package.json.
FROM oven/bun:1.3.11 AS bun
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=1 \
    TURBO_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates curl git python3 pkg-config \
      ripgrep unzip zip file \
    && rm -rf /var/lib/apt/lists/*
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s /usr/local/bin/bun /usr/local/bin/bunx

# The scanner supplies an anonymous public checkout as the build context.
COPY . /src
WORKDIR /src

# tools/check removes this file before building an adjacent Dockerfile so the
# full source reaches the image. Restore it for source-contract tests; Docker
# has already selected and copied the build context at this point.
RUN git show HEAD:.dockerignore > .dockerignore

# Match contributor CI: install the locked workspace without desktop downloads
# or Git-hook installation, then build the source-owned office dependencies.
# The server and agent execute TypeScript directly with Bun.
RUN bun install --frozen-lockfile --ignore-scripts
# Build the Linux PTY binding against the headers already in the Node image,
# so process-execution reproducers do not need downloads during the audit.
RUN npm rebuild --prefix /src/node_modules/node-pty --nodedir=/usr/local \
    && bun dev/scripts/fix-node-pty-perms.ts
RUN bun run writer:prepare \
    && bun run first-party-apps:install \
    && bun run board:prepare
RUN bun run --cwd packages/workbench-components build \
    && bun run --cwd apps/workbench build

# Fail the build if the basic security test environment is unusable. Additional
# suites and platform/integration requirements are documented in threat_model.md.
RUN bun run --cwd packages/security test:unit \
    && bun run --cwd packages/trust test:unit \
    && bun run --cwd packages/desktop-filesystem-grants test:unit

CMD ["bash"]
