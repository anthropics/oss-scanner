# Mandate enrollment build for Anthropic OSS Scanner.
# Builds the full TypeScript workspace and the Rust workspace so the offline
# security audit can exercise the real artifacts. Network is available while
# this Dockerfile builds and is removed afterwards; everything below must
# leave the image self-sufficient.
FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/pnpm:$PATH

# perl: required to compile the vendored OpenSSL inside rusqlite's
# bundled-sqlcipher feature. cmake/pkg-config/clang: -sys crates.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang cmake pkg-config \
      git python3 curl perl \
    && rm -rf /var/lib/apt/lists/*

# pnpm: the repo pins pnpm@10.22.0 via the packageManager field.
RUN corepack enable && corepack prepare pnpm@10.22.0 --activate && pnpm --version

# Rust stable toolchain (the repo pins stable via rust-toolchain.toml).
# Debug info + frame pointers so the scanner's reproducers get usable traces.
ENV RUSTFLAGS="-g -C force-frame-pointers=yes"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain stable \
    && rustc --version && cargo --version

# Scanner contract: the checkout lives inside the image at /src.
COPY . /src
WORKDIR /src

# TypeScript workspace: fetch every dependency, then build each package that
# defines a build script (video/ defines none and is skipped by --if-present).
RUN pnpm install --frozen-lockfile
RUN pnpm -r --if-present build

# Rust workspace (mandate-core, mandated, mandate): prefetch all crates with
# network, then build everything offline-capable.
RUN cargo fetch --locked
RUN cargo build --locked --workspace

# Cheap tests so the image is known to work. Failures warn but do not abort
# the image build; the scanner still gets a fully built project to audit.
RUN (pnpm -r --if-present test || echo "WARNING: pnpm tests reported failures")
RUN (cargo test --locked --workspace || echo "WARNING: cargo tests reported failures")
