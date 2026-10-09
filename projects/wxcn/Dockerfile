FROM node:26-bookworm

ENV CI=true \
    DO_NOT_TRACK=1 \
    ASTRO_TELEMETRY_DISABLED=1 \
    WRANGLER_SEND_METRICS=false

# Install the package manager declared by the project's package.json.
RUN npm install --global pnpm@12.9.1

# The scanner expects the full checkout, dependencies, and build outputs in /src.
COPY . /src
WORKDIR /src
RUN pnpm install --frozen-lockfile
RUN pnpm build && pnpm build:react && pnpm build:vue

# Unit/SSR tests require no live services. Retain failures in the build log,
# while leaving the project available for investigation as in the template.
RUN pnpm test && pnpm test:react && pnpm test:vue || { echo "WARNING: tests reported failures; inspect the build log"; }

CMD ["bash"]
