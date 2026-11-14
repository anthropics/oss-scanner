FROM node:24.18.0-bookworm-slim
COPY --from=oven/bun:1.4.2 /usr/local/bin/bun /usr/local/bin/bun
ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    EXECUTOR_BUILD_VERSION=oss-scanner \
    EXECUTOR_ENVIRONMENT=self-host
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates python3 make g++ curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# Keep source, dependencies and build outputs available to the offline audit.
COPY . /src
WORKDIR /src
RUN bun install --frozen-lockfile
RUN bun x --no-install playwright install --with-deps chromium
RUN bun run apps:build
RUN bun run telemetry:build
RUN bun run e2e:runtime && bun run e2e:apps
RUN bun run web:build && bun run hosted:self-host:web:build
RUN bun run --cwd apps/hosted/self-host package:runtime
RUN bun run e2e:pglite
CMD ["bash"]
