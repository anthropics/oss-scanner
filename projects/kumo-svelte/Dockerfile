FROM node:26-bookworm

ENV CI=true \
    DO_NOT_TRACK=1 \
    ASTRO_TELEMETRY_DISABLED=1 \
    WRANGLER_SEND_METRICS=false

# Install the package manager declared by the project's package.json.
RUN npm install --global pnpm@11.10.0

# The scanner expects the full checkout, dependencies, and build outputs in /src.
COPY . /src
WORKDIR /src
RUN pnpm install --frozen-lockfile
RUN pnpm build:package && pnpm build

# Unit/SSR tests require no live services. Retain failures in the build log,
# while leaving the project available for investigation as in the template.
RUN pnpm --filter kumo-svelte exec vitest run --maxWorkers=2 && pnpm test:tools || { echo "WARNING: tests reported failures; inspect the build log"; }

CMD ["bash"]
