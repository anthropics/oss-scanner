# Archestra platform (platform/): Fastify backend, Next.js frontend and Rust N-API addons.
# Mirrors the builder stages of platform/Dockerfile on Debian, and keeps the checkout, every
# dependency, the build outputs and a migrated local PostgreSQL for the offline audit.
FROM node:24.22.2-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Build tools, plus PostgreSQL 18 with pgvector from the PostgreSQL project's repository
# (bookworm's own pgvector predates HNSW indexes). No cluster is created here.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential pkg-config libssl-dev python3 jq procps postgresql-common \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && sed -i 's/^#*\s*create_main_cluster.*/create_main_cluster = false/' /etc/postgresql-common/createcluster.conf \
 && apt-get install -y --no-install-recommends postgresql-18 postgresql-18-pgvector \
 && rm -rf /var/lib/apt/lists/*

# Rust: rustup only; the toolchain itself comes from platform/rust-toolchain.toml below.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    OPENSSL_NO_VENDOR=1 \
    PATH=/usr/local/cargo/bin:/usr/lib/postgresql/18/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --no-modify-path --profile minimal --default-toolchain none

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/platform

# Local-only settings. The two PREBUILT switches stop the dev scripts from downloading CI's
# builds: everything is compiled here, and nothing may reach the network after this build.
ENV CI=true \
    NEXT_TELEMETRY_DISABLED=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    ARCHESTRA_ANALYTICS=disabled \
    ARCHESTRA_DEV_NAPI_PREBUILT=false \
    ARCHESTRA_DEV_FRONTEND_PREBUILT=false

# pnpm at the version package.json pins, and the Rust toolchain rust-toolchain.toml pins.
RUN corepack enable && corepack install && pnpm --version \
 && rustup toolchain install && cargo --version

# Install scripts stay off, as the repository configures (ignoreScripts).
RUN pnpm install --frozen-lockfile

# The five N-API addons, as the released image builds them. Then fetch every crate in the lock
# file, so `cargo test` works with no network.
RUN pnpm --workspace-concurrency=1 \
      --filter @archestra/sandbox-rs \
      --filter @archestra/app-runtime-rs \
      --filter @archestra/image-rs \
      --filter @archestra/openappa-rs \
      --filter @archestra/router-rs build \
 && (cd archestra-rs && cargo fetch --locked)

# Backend (backend/dist) and frontend (frontend/.next, with its standalone server).
RUN pnpm exec turbo build --filter=@backend --filter=@frontend --filter=@archestra/shared --only \
 && cp -R frontend/.next/static frontend/.next/standalone/frontend/.next/static \
 && cp -R frontend/public frontend/.next/standalone/frontend/public

# `archestra-db start|stop|status` runs the local PostgreSQL as the postgres user (the server
# refuses to run as root): archestra@127.0.0.1:5432/archestra_dev, trust authentication.
RUN printf '%s\n' \
      '#!/bin/sh' \
      '# Local PostgreSQL 18 (pgvector) for Archestra: archestra@127.0.0.1:5432/archestra_dev, trust auth.' \
      'exec runuser -u postgres -- /usr/lib/postgresql/18/bin/pg_ctl -D /var/lib/archestra-pg -w -t 90 \' \
      '  -l /var/lib/archestra-pg/server.log \' \
      '  -o "-c listen_addresses=127.0.0.1 -c fsync=off -c synchronous_commit=off -c full_page_writes=off" \' \
      '  "${1:-start}"' \
      > /usr/local/bin/archestra-db \
 && chmod +x /usr/local/bin/archestra-db

# platform/.env from the example (it already points at the database above), without Kubernetes:
# a kubeconfig path that does not exist makes the MCP orchestrator disable itself at startup.
# Then create the cluster and run every migration, so the image is known to hold a working schema.
RUN cp .env.example .env \
 && sed -i 's|^ARCHESTRA_ORCHESTRATOR_KUBECONFIG=.*|ARCHESTRA_ORCHESTRATOR_KUBECONFIG=/nonexistent/no-kubernetes.kubeconfig|' .env \
 && sed -i 's|^ARCHESTRA_ANALYTICS=.*|ARCHESTRA_ANALYTICS=disabled|' .env \
 && install -d -o postgres -g postgres -m 0700 /var/lib/archestra-pg \
 && runuser -u postgres -- initdb -D /var/lib/archestra-pg -U archestra --auth=trust -E UTF8 \
 && archestra-db start \
 && createdb -h 127.0.0.1 -U archestra archestra_dev \
 && pnpm --dir backend db:migrate \
 && archestra-db stop

# Cheap tests, so the log shows the image works. A failing test must not abort the build.
RUN pnpm --dir shared test || echo "WARNING: shared tests reported failures"
RUN (cd archestra-rs && cargo test --locked -p router_core) || echo "WARNING: router_core tests reported failures"

# From here on there is no network: make cargo say so at once instead of timing out.
ENV CARGO_NET_OFFLINE=true
