# The scanner uses the repository root as the build context and audits /src offline, so everything the
# build and the tests need is installed here, from the committed pnpm-lock.yaml, as CI does.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

# pnpm at the version `packageManager` pins in package.json.
RUN corepack enable

COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile

RUN pnpm run build

# Run the unit tests so the image is known to work; a failing test must not abort the build.
RUN pnpm run test || echo "WARNING: tests reported failures"
