# TUICommander: SolidJS/Vite frontend (src/), Tauri 2 desktop shell and Rust workspace (src-tauri/), with the
# tuic-bridge MCP sidecar, the tuic CLI and the tuic-remote daemon. Versions follow .github/workflows/ci.yml
# (job `rust`, Ubuntu 22.04, RUST_VERSION) and package.json (packageManager).
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
# Line 2 is the Tauri/WebKitGTK and audio set from ci.yml; line 3 builds whisper.cpp (dictation) and the bundled
# WebRTC audio processing; fish and zsh run the shell-integration launch matrix in the tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils build-essential pkg-config file \
      libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf libasound2-dev libssl-dev \
      cmake clang libclang-dev python3-pip fish zsh \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir meson ninja

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# src-tauri embeds the bundled plugins with include_str!; they live in the `plugins` submodule.
RUN if [ ! -f plugins/plan/manifest.json ]; then \
      if [ -d .git ]; then git submodule update --init --recursive; \
      else rm -rf plugins && git clone --depth 1 https://github.com/sstraus/tuicommander-plugins.git plugins; fi; \
    fi && test -f plugins/plan/manifest.json

# Node 24 (ci.yml) and the pnpm version from package.json, through corepack.
RUN node_url=https://nodejs.org/dist/latest-v24.x; \
    node_arch="$(dpkg --print-architecture | sed 's/amd64/x64/')"; \
    tarball="$(curl -fsSL "$node_url/SHASUMS256.txt" | awk -v want="-linux-$node_arch.tar.xz" '$2 ~ want "$" { print $2 }')"; \
    curl -fsSL "$node_url/$tarball" | tar -xJ -C /usr/local --strip-components=1 \
    && corepack enable && corepack install && node --version && pnpm --version

# The Rust version pinned in ci.yml, plus cargo-nextest for the test suite.
RUN rust_version="$(awk -F'"' '/^  RUST_VERSION:/ { print $2; exit }' .github/workflows/ci.yml)"; \
    printf '%s\n' "$rust_version" | grep -Eqx '[0-9]+\.[0-9]+(\.[0-9]+)?' \
    && curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain "$rust_version" --no-modify-path \
    && ln -s /root/.cargo/bin/* /usr/local/bin/ \
    && case "$(dpkg --print-architecture)" in arm64) nextest=linux-arm ;; *) nextest=linux ;; esac \
    && curl -fsSL "https://get.nexte.st/latest/$nextest" | tar -xz -C /usr/local/bin

# Frontend: dependencies and the production build that the desktop binary embeds (dist/).
RUN pnpm install --frozen-lockfile && pnpm build

# The root crate's lib and lib-test compiles need ~10 GB each. Unset, cargo uses every CPU; set it with
# --build-arg on a machine with less than ~32 GB of memory.
ARG CARGO_BUILD_JOBS
# Cargo fingerprints a path crate whose build script has no rerun-if-changed by the newest mtime of its files, with
# nanoseconds. Image layers keep whole seconds only, so without this every later cargo command rebuilds the root crate.
# Tauri's build.rs needs the sidecar files: build them first, copy them in place, then build everything else.
# `cargo test --no-run` builds the same graph that cargo test and cargo nextest use; --all-targets would also pull
# in benches and examples, change feature unification and leave the test graph unbuilt.
# CARGO_INCREMENTAL=0 as in ci.yml: incremental data would add tens of GB to target/ for no use in a one-off build.
ENV CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C target-cpu=x86-64" \
    CARGO_INCREMENTAL=0
RUN find /src -path /src/src-tauri/target -prune -o -exec touch -h -d @1767225600 {} + \
    && cd src-tauri && target="$(rustc --print host-tuple)" \
    && cargo build -p tuic-bridge -p tuic-cli \
    && cp target/debug/tuic-bridge "binaries/tuic-bridge-$target" \
    && cp target/debug/tuic "binaries/tuic-$target" \
    && cargo test --no-run --workspace --features dictation,test-fixtures \
    && cargo build --no-default-features --bin tuic-remote

# Every cargo test run re-links target/debug/tuic-remote as the desktop stub; keep the headless daemon elsewhere.
RUN cp src-tauri/target/debug/tuic-remote /usr/local/bin/tuic-remote

# nextest runs `cargo metadata --all-features`, which needs every crate in Cargo.lock, including optional and
# other-platform ones the build did not download. The scan runs without network access.
RUN cd src-tauri && cargo fetch
ENV CARGO_NET_OFFLINE=true
# Tests (offline): cd src-tauri && cargo nextest run --workspace --features dictation,test-fixtures
#                  pnpm exec vitest run
