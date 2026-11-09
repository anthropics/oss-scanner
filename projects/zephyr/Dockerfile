# Scanner image for https://github.com/Juwan-Hwang/Zephyr (main).
#
# Zephyr is a Tauri 2 + Rust workspace (apps/desktop + crates/) with a JavaScript frontend that
# ships as plain HTML/JS from apps/desktop/src (tauri.conf.json points frontendDist at ../src, so
# there is no bundler step for the app itself; only generated CSS/token files and a CodeMirror
# bundle are produced from the frontend sources).
#
# The build below mirrors the project's own CI (.github/workflows/ci.yml) on purpose: the same
# pinned Rust toolchain (rust-toolchain.toml: 1.96.0), the same Linux system packages, and the
# same pnpm install flags. The audit runs offline, so every crates.io and npm dependency is
# fetched during this build.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive

# Build tools plus the Tauri / WebKitGTK system libraries CI installs on Ubuntu; bookworm ships
# the same libwebkit2gtk-4.1, libappindicator3 and librsvg2 development packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential clang pkg-config python3 \
      libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf xdg-utils \
      libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS (the repo requires >= 20.18.1) and pnpm via corepack, which honours the
# packageManager pin in package.json (pnpm 10.12.1).
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable

# Rust at the channel pinned in rust-toolchain.toml, with the components CI uses.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
      --default-toolchain 1.96.0 --component rustfmt,clippy
ENV PATH="/root/.cargo/bin:${PATH}"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Frontend dependencies, installed exactly as CI does: --ignore-scripts skips the husky
# "prepare" hook (it needs a git checkout), then the two allow-listed native deps are rebuilt.
RUN pnpm install --frozen-lockfile --ignore-scripts && pnpm rebuild esbuild @parcel/watcher

# Generate the frontend assets the desktop app serves (design-token CSS and UnoCSS output),
# i.e. the beforeBuildCommand work of a real Tauri build. The CodeMirror bundle
# (src/cm6.bundle.js) is committed in the repository, so it needs no build step here.
RUN pnpm --filter @zephyr/desktop build:css

# Build the whole Rust workspace in the dev profile (debug info on, like CI's debug test
# profile). This builds the zephyr desktop binary and every workspace crate and test target.
RUN cargo build --workspace --all-targets --locked

# Run the test suites the way CI does, but never fail the image build on a red test (per the
# scanner template): the point of this step is a working image with tests exercised.
RUN (cargo test --workspace --locked || echo "WARNING: cargo test reported failures")
RUN (pnpm -r test || echo "WARNING: frontend tests reported failures")
