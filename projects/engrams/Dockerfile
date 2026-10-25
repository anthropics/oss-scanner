# syntax=docker/dockerfile:1
# engrams is a Rust workspace (coordinator, host agent, in-guest daemon, egress
# proxy, CLI) plus two TypeScript packages: the orchestrator (Bun) and the web
# dashboard (pnpm). rust-toolchain.toml pins the stable channel; rustup installs
# it during the first cargo call below. Debug builds keep line tables (not full
# DWARF), compressed at link time, so the workspace build fits on disk;
# backtraces still have file:line.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1 \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C link-arg=-Wl,--compress-debug-sections=zlib" \
    CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C link-arg=-Wl,--compress-debug-sections=zlib" \
    SQLX_OFFLINE=true \
    ENGRAM_TEST_DATABASE_URL=postgres://postgres:engram@127.0.0.1:5432/engram_test

# protobuf-compiler: engram-protocol's build.rs runs protoc.
# clang + libclang-dev: userfaultfd-sys runs bindgen against <linux/userfaultfd.h>.
# make: tikv-jemalloc-sys builds the vendored jemalloc.
# squashfs-tools, e2fsprogs: the skill packer and rootfs materializer shell out to them.
# postgresql: the live-Postgres tests (ignored by default) need a server.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip pkg-config libssl-dev protobuf-compiler \
      clang libclang-dev make python3 squashfs-tools e2fsprogs postgresql \
    && rm -rf /var/lib/apt/lists/*

# Node 24 + pnpm 9 for web/, Bun (version from .bun-version) for orchestrator/.
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g pnpm@9

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

RUN curl -fsSL https://bun.sh/install | bash -s "bun-v$(cat .bun-version)" \
    && ln -s /root/.bun/bin/bun /usr/local/bin/bun

# cargo-nextest: the test suite expects one process per test (some tests set
# environment variables that are read once per process).
RUN case "$(uname -m)" in aarch64) p=linux-arm ;; *) p=linux ;; esac \
    && curl -LsSf "https://get.nexte.st/latest/$p" | tar zxf - -C /usr/local/cargo/bin

# Fetch every crate so later builds work with --offline.
RUN cargo fetch --locked

# Build every workspace binary. The macOS-only VZ backend compiles to an empty
# crate on Linux. Integration-test binaries are not built here: each one links
# the whole dependency tree, and together they do not fit on the build disk.
# Every crate is fetched, so `cargo nextest run --offline -p <crate>` builds
# them on demand.
RUN cargo build --locked --workspace --bins

# Install the TypeScript dependencies so the orchestrator and web tests run offline.
RUN cd orchestrator && bun install --frozen-lockfile \
    && cd ../web && pnpm install --frozen-lockfile

# Set a password for the local Postgres so the live-PG tests can connect.
RUN service postgresql start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'engram'\"" \
    && su postgres -c "createdb engram_test" \
    && service postgresql stop

# Build and run the unit tests as a smoke check. Failures do not abort the build.
RUN (timeout 1800 cargo nextest run --locked --workspace --lib \
      || echo "WARNING: Rust unit tests reported failures")
RUN (cd orchestrator && bun run typecheck || echo "WARNING: orchestrator typecheck failed")
