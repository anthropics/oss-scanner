# helium-onboarding is the Svelte page Helium shows at helium://setup. This image installs its dependencies and
# builds it the way CI does (.github/workflows/ci.yml).
FROM node:24-trixie-slim
ENV DEBIAN_FRONTEND=noninteractive \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# pnpm at the version pinned by packageManager in package.json, fetched now so it works offline.
RUN corepack enable pnpm && pnpm --version

RUN pnpm install --frozen-lockfile && pnpm build
RUN pnpm check || echo "WARNING: pnpm check reported problems"
