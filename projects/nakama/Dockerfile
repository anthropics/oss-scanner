# Dev image for the scanner: full checkout, all dependencies (dev included),
# so tests and type checks run with no network after the build.
FROM oven/bun:1.4.4
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# --ignore-scripts skips husky and the docs site install.
RUN bun install --frozen-lockfile --ignore-scripts

# Cheap check that the image works. A failure does not stop the build.
RUN (bun test --parallel=4 --path-ignore-patterns '**/apps/web/**' --timeout 30000 \
      || echo "WARNING: bun test reported failures")
