FROM node:22.20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates git g++ make python3 openssl \
      libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*
RUN npm --no-update-notifier --no-fund --global install pnpm@10.6.1

# Keep the source, development dependencies and build outputs for the offline audit.
COPY . /src
WORKDIR /src

# Local-only settings for reproductions; no production credentials are needed.
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=4096 \
    DATABASE_URL=postgresql://postiz:postiz@localhost:5432/postiz \
    REDIS_URL=redis://localhost:6379 \
    JWT_SECRET=oss-scanner-local-only-not-a-production-secret \
    FRONTEND_URL=http://localhost:4200 \
    NEXT_PUBLIC_BACKEND_URL=http://localhost:3000 \
    BACKEND_INTERNAL_URL=http://localhost:3000 \
    STORAGE_PROVIDER=local \
    UPLOAD_DIRECTORY=/src/uploads \
    NEXT_PUBLIC_UPLOAD_STATIC_DIRECTORY=/src/uploads \
    IS_GENERAL=true

# Run setup separately so Prisma uses the CLI already pinned in the lockfile,
# without a second dependency resolution through the upstream pnpm dlx script.
RUN NODE_OPTIONS=--max-old-space-size=2048 pnpm install --frozen-lockfile --ignore-scripts
RUN pnpm rebuild bcrypt \
    && pnpm exec prisma generate --schema ./libraries/nestjs-libraries/src/database/prisma/schema.prisma \
    && pnpm --filter ./apps/frontend run fetch-gtm
RUN pnpm -r --workspace-concurrency=1 --filter ./apps/backend --filter ./apps/orchestrator run build
# Use the frontend's existing Webpack configuration and retain its source maps.
RUN pnpm --filter ./apps/frontend run build --webpack

# Preserve test failures in the build log without preventing security analysis.
RUN pnpm run test --runInBand || echo "WARNING: Postiz's test command failed; inspect its output above."
