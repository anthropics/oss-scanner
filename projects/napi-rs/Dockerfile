FROM node:24-bookworm AS node
FROM rust:1-bookworm

# The scanner uses Linux x86-64. On ARM hosts, build with
# DOCKER_DEFAULT_PLATFORM=linux/amd64 (also for tools/check).
COPY --from=node /usr/local/ /usr/local/
ENV DEBIAN_FRONTEND=noninteractive \
    HUSKY=0 \
    ELECTRON_SKIP_BINARY_DOWNLOAD=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    CARGO_PROFILE_DEV_DEBUG=2 \
    CARGO_PROFILE_DEV_OPT_LEVEL=1 \
    CARGO_BUILD_JOBS=2 \
    RUSTFLAGS="-C force-frame-pointers=yes" \
    YARN_ENABLE_TELEMETRY=0
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang cmake pkg-config python3 libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src
RUN ln -sf /src/.yarn/releases/yarn-*.cjs /usr/local/bin/yarn \
    && yarn install --immutable --mode=skip-build \
    && cargo fetch

# Preserve dependencies, Cargo.lock, source, debug symbols and build outputs so
# the scanner can modify and rebuild the project without Internet access.
ENV CARGO_NET_OFFLINE=true \
    YARN_ENABLE_NETWORK=0
RUN yarn build \
    && yarn workspace @examples/napi build \
    && yarn workspace @examples/compat-mode build \
    && yarn workspace @examples/custom-async-runtime build \
    && yarn workspace @examples/shared-async-runtime build \
    && cargo test --workspace --no-run

# Small native smoke test; the full offline test commands are in threat_model.md.
RUN node -e "require('./examples/napi/index.cjs')"
