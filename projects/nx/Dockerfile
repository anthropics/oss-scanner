# Builds the nrwl/nx monorepo the way its CI does: toolchains from mise.toml, pnpm via corepack, then the
# `nx` package (TypeScript + the Rust native binding). The workspace graph loads the Gradle, Maven and .NET
# plugins, so Java, Maven and .NET are installed too, and their dependency caches are warmed while online.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg unzip xz-utils build-essential clang pkg-config python3 libicu72 \
    && rm -rf /var/lib/apt/lists/*

ENV HOME=/root \
    MISE_DATA_DIR=/opt/mise \
    MISE_CACHE_DIR=/opt/mise/cache \
    MISE_YES=1 \
    MISE_GLOBAL_CONFIG_FILE=/src/mise.toml \
    PATH=/opt/mise/shims:/root/.cargo/bin:$PATH
RUN curl -fsSL https://mise.run | MISE_INSTALL_PATH=/usr/local/bin/mise sh && mise --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# CI=true skips the interactive toolchain checks and git hooks. Nx Cloud and the daemon stay off so
# every task runs locally and nothing reaches for the network after the build.
ENV CI=true \
    NX_NO_CLOUD=true \
    NX_DAEMON=false \
    NX_TUI=false \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    CARGO_INCREMENTAL=0

RUN mise trust /src/mise.toml && mise install && mise reshim
RUN corepack enable && corepack prepare --activate && mise reshim && pnpm --version
RUN pnpm install --frozen-lockfile
RUN dotnet restore nx.sln

# BuildKit's /etc/hosts lists localhost as both 127.0.0.1 and ::1. Verdaccio binds one and Node clients dial the
# other unless Node resolves IPv4 first.
ENV NODE_OPTIONS=--dns-result-order=ipv4first

# Builds every public package, publishes them to a local Verdaccio registry in dist/local-registry/storage,
# and creates installed workspaces from that release in dist/local-registry/proj-backup, as Nx's e2e suite
# does. Computing the project graph also downloads the Gradle, Maven and NuGet dependencies needed offline.
RUN pnpm nx populate-e2e-base-workspace --outputStyle=stream
RUN cargo fetch --manifest-path /src/Cargo.toml

# Cheap tests, so a broken image is visible in the build log without failing the build.
RUN pnpm nx test-native nx --outputStyle=stream || echo "WARNING: nx test-native nx reported failures"
# Several specs assert cloud behavior and fail when NX_NO_CLOUD is set, so vitest runs without it.
RUN cd packages/nx && env -u NX_NO_CLOUD npx vitest run || echo "WARNING: vitest reported failures"
