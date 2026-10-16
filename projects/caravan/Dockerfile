# Builds the Caravan monorepo (coordinator app and @caravan/* packages) the way its CI does.
# Network access is only available during this build, so every dependency is installed here.
FROM node:24-bookworm

ENV CI=true \
    HUSKY=0 \
    TURBO_TELEMETRY_DISABLED=1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci

RUN NODE_OPTIONS=--max-old-space-size=8192 npx turbo run build

# Unit tests (vitest) for every package and the coordinator. Failures are reported but do not fail the build.
RUN npx turbo run test --continue || echo "WARNING: turbo test reported failures"
