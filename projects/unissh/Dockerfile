# Scanner image for https://github.com/goduni/unissh (main): every part that ships to users.
#   - the root Cargo workspace: the core crates under rust-core/crates and the unissh-server sync server;
#   - the desktop client: its React front end (client/) and its Tauri crate (client/src-tauri, a separate workspace);
#   - the admin panel: its React front end (server-ui/) and its wasm crypto (server-ui/crypto-wasm, a separate
#     workspace).
#
# The audit runs offline, so this build installs the pinned toolchain, Node and wasm-pack, fetches every crate and npm
# package the three Cargo workspaces and two front ends lock, then builds all of them and their test binaries, as CI
# does, so the tests can run offline.

# The image CI's test job runs in.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# libssl-dev and clang build bundled SQLCipher. sshd and ssh-keygen back the integration tests in ssh-transport,
# ssh-agent and ffi, which spawn their own sshd and log in as root. The GTK/WebKit libraries are what CI installs to
# build the Tauri client on Linux.
RUN apt-get update && apt-get install -y --no-install-recommends \
      pkg-config libssl-dev clang openssh-server openssh-client \
      libwebkit2gtk-4.1-dev libgtk-3-dev libsoup-3.0-dev libjavascriptcoregtk-4.1-dev \
      librsvg2-dev libxdo-dev libayatana-appindicator3-dev xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd

# Node 22, the version both front-end workflows use.
COPY --from=node:22-bookworm /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never

# rust-toolchain.toml pins the channel; install it now, while the network is up, with the wasm target the admin panel
# needs.
RUN rustup show active-toolchain || rustup toolchain install \
    && rustup target add wasm32-unknown-unknown

# wasm-pack, at the version CI pins, as the release binary rather than built from source. x86-64 only.
ARG WASM_PACK_VERSION=0.13.1
ARG WASM_PACK_SHA256=c539d91ccab2591a7e975bcf82c82e1911b03335c80aa83d67ad25ed2ad06539
RUN curl -fsSL -o /tmp/wasm-pack.tar.gz \
      "https://github.com/rustwasm/wasm-pack/releases/download/v${WASM_PACK_VERSION}/wasm-pack-v${WASM_PACK_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    && echo "${WASM_PACK_SHA256}  /tmp/wasm-pack.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/wasm-pack.tar.gz -C /usr/local/bin --strip-components=1 \
      "wasm-pack-v${WASM_PACK_VERSION}-x86_64-unknown-linux-musl/wasm-pack" \
    && rm /tmp/wasm-pack.tar.gz \
    && wasm-pack --version

# Every crate in the three Cargo.lock files and every package in the two package-lock.json files, so later builds stay
# offline.
RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path client/src-tauri/Cargo.toml \
    && cargo fetch --locked --manifest-path server-ui/crypto-wasm/Cargo.toml \
    && (cd client && npm ci --include=optional --no-audit --no-fund) \
    && (cd server-ui && npm ci --no-audit --no-fund)

# A step that fails fails the build, and primary_contact gets the log.

# The root workspace with the features CI tests: libraries, binaries and every test binary.
RUN cargo build --locked --workspace --features unissh-automation/core --lib --bins \
    && cargo test --locked --workspace --features unissh-automation/core --no-run

# The desktop client. The Tauri crate embeds client/dist when it compiles, so the front end is built first.
RUN (cd client && npm run build) \
    && cargo build --locked --manifest-path client/src-tauri/Cargo.toml \
    && cargo test --locked --manifest-path client/src-tauri/Cargo.toml --no-run

# The admin panel. Its front end imports the wasm package that wasm-pack writes to crypto-wasm/pkg.
RUN (cd server-ui/crypto-wasm && wasm-pack build --target web --out-dir pkg --dev) \
    && (cd server-ui && npm run build)

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
