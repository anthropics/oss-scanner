FROM oven/bun:1
ENV DEBIAN_FRONTEND=noninteractive \
    NEXT_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git openssl python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN bun install --frozen-lockfile --ignore-scripts

# Production build (same step as docker/web/Dockerfile); the database is a throwaway file.
RUN DATABASE_PATH=/tmp/build.db DATABASE_URL=file:/tmp/build.db NODE_ENV=production bun run build \
    && rm -f /tmp/build.db

# Cheap unit tests; a failure must not abort the build.
RUN (bun run test || echo "WARNING: tests reported failures")
