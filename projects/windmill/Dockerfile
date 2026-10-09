# Windmill for the OSS Scanner: an open-source debug build of the backend with the frontend embedded, a local
# Postgres, and the bun / deno / python runtimes, so a standalone instance starts with no network (`wm-start`).
# Only what is in the public repository is built: the enterprise sources are not part of it.

FROM debian:trixie-slim AS nsjail
WORKDIR /nsjail
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates bison flex g++ gcc git libprotobuf-dev libnl-route-3-dev make pkg-config protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
# the commit the project's own Dockerfile builds
RUN git clone -b master --single-branch https://github.com/google/nsjail.git . \
    && git checkout dccf911fd2659e7b08ce9507c25b2b38ec2c5800 \
    && make -j"$(nproc)"


# Built in its own stage so it runs alongside the backend's dependency fetch.
FROM node:24-trixie-slim AS frontend
COPY . /src
WORKDIR /src/frontend
RUN npm ci
RUN npm run generate-backend-client
# The backend embeds frontend/build. If the bundle fails the backend still builds, and serves no UI.
RUN NODE_OPTIONS=--max-old-space-size=8192 npm run build \
    || echo "WARNING: the frontend bundle failed, the instance will serve the API only"


FROM rust:1.97-slim-trixie
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip jq procps build-essential pkg-config cmake clang libclang-dev mold \
      libssl-dev libkrb5-dev libsasl2-dev libcurl4-openssl-dev \
      postgresql postgresql-client \
      libprotobuf32t64 libnl-route-3-200 libnl-3-200 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*
RUN rustup component add rustfmt clippy

# Job runtimes, at the versions and paths of the project's own image.
COPY --from=nsjail /nsjail/nsjail /bin/nsjail
COPY --from=denoland/deno:2.2.1 --chmod=755 /usr/bin/deno /usr/bin/deno
COPY --from=oven/bun:1.4.0 /usr/local/bin/bun /usr/bin/bun
ENV UV_PYTHON_INSTALL_DIR=/tmp/windmill/cache/py_runtime \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_CACHE_DIR=/tmp/windmill/cache/uv
RUN curl --proto '=https' --tlsv1.2 -LsSf https://github.com/astral-sh/uv/releases/download/0.11.24/uv-installer.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && uv python install 3.12 --compile-bytecode \
    && mkdir -p -m 777 /tmp/windmill/cache/uv /tmp/windmill/logs

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/backend

# The committed .sqlx cache type-checks the queries, so the build needs no database.
ENV SQLX_OFFLINE=true
RUN cargo fetch

COPY --from=frontend /src/frontend /src/frontend

# The `oss` edition without `no_auth` (which disables authentication) and without `duckdb` (its engine is a long
# C++ build of its own). Debug profile: line tables and frame pointers are kept, and target/ stays in the image so
# a patched crate rebuilds incrementally.
ARG FEATURES="oss_core,python,deno_core,rust,mysql,oracledb,mssql-kerberos,bigquery,snowflake,csharp,nu,php,java,ruby,rlang"
# RUSTFLAGS replaces the rustflags of backend/.cargo/config.toml instead of adding to them, so the mold link
# argument set there is repeated here.
ENV WM_FEATURES=$FEATURES \
    RUSTFLAGS="-C force-frame-pointers=yes -C link-arg=-fuse-ld=mold"
RUN cargo build --features "$FEATURES"

# Everything is fetched: later cargo commands (cargo test, a rebuild after a patch) must not try the network.
ENV CARGO_NET_OFFLINE=true

COPY --chmod=755 <<'EOF' /usr/local/bin/wm-db
#!/bin/bash
# wm-db start|stop: the Postgres cluster bundled in this image (postgres:changeme@127.0.0.1:5432/windmill)
pg_lsclusters -h | while read -r version name _; do pg_ctlcluster "$version" "$name" "$1"; done
if [ "$1" = start ]; then
  for _ in $(seq 1 60); do pg_isready -q -h 127.0.0.1 && exit 0; sleep 1; done
  echo "postgres did not start" >&2; exit 1
fi
EOF

COPY --chmod=755 <<'EOF' /usr/local/bin/wm-start
#!/bin/bash
# Starts Postgres and a standalone Windmill (API server + one worker) on http://127.0.0.1:8000.
# Log in as admin@windmill.dev / changeme. Extra environment (DISABLE_NSJAIL=false, MODE=server, ...) passes through.
set -e
wm-db start
export DATABASE_URL="${DATABASE_URL:-postgres://postgres:changeme@127.0.0.1:5432/windmill}"
export DISABLE_EMBEDDING="${DISABLE_EMBEDDING:-true}"
cd /src/backend
exec ./target/debug/windmill "$@"
EOF

RUN wm-db start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'changeme'\"" \
    && su postgres -c "createdb windmill" \
    && wm-db stop

# Smoke test: boot the instance once, which also applies the migrations to the bundled database. A failure is
# reported in the build log and does not abort the build.
RUN (wm-start > /tmp/wm-smoke.log 2>&1 & \
      for _ in $(seq 1 240); do curl -fsS http://127.0.0.1:8000/api/version > /dev/null 2>&1 && break; sleep 1; done; \
      if curl -fsS http://127.0.0.1:8000/api/version; then echo " <- windmill is up"; \
      else echo "WARNING: windmill did not come up"; tail -n 80 /tmp/wm-smoke.log; fi; \
      pkill -x windmill; sleep 3; wm-db stop) || echo "WARNING: smoke test failed"

WORKDIR /src
