# Keep OpenClaw's source, development dependencies, and build outputs available
# to the scanner. The upstream production image deliberately prunes them.
# Base images match the pins in openclaw/openclaw's Dockerfile.
FROM docker.io/oven/bun:1.4.2@sha256:9114c058aeae42162ee16dd5084b95fe9473970bb6bcb5b232ab1630f0546895 AS bun
FROM docker.io/library/node:24-bookworm@sha256:64af3819f9275802414d7cdc38c27e9d82bd564dec4d4da87d008255d36c63b4

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake curl git libpam0g-dev \
        pkg-config python3 ripgrep unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
RUN corepack enable

# tools/check supplies a clean upstream checkout as the build context.
COPY . /src
WORKDIR /src

# Use the packageManager pin and frozen workspace lockfile, including the
# repository's dependency patches and native-addon build policy.
RUN pnpm install --frozen-lockfile

# Cache the browser and its OS dependencies while networking is available.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    OPENCLAW_PREFER_PNPM=1
RUN pnpm exec playwright install --with-deps chromium

# The normal development build includes the CLI, packages, plugin assets,
# native protocol sources, and Control UI. Retain declarations and test tools.
RUN pnpm build

CMD ["bash"]
