FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS node
FROM rust:1.99.0-bookworm@sha256:59037199c44290f2befcdd58dcc540164763fc296950255aaefeef096a1866b0

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git bash python3 build-essential pkg-config file libssl-dev \
    libwebkit2gtk-4.1-dev libjavascriptcoregtk-4.1-dev libsoup-3.0-dev \
    libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev libdbus-1-dev \
    dbus gnome-keyring xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src
ENV CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1

# The desktop shell embeds the renderer, so compile it before the Rust workspace.
RUN rustup toolchain install stable --profile minimal --component rustfmt --component clippy \
    && npm --prefix apps/desktop ci --no-audit --no-fund \
    && npm --prefix apps/desktop run build \
    && cargo fetch --locked \
    && cargo build --locked --workspace \
    && cargo test --locked --workspace --no-run

CMD ["bash"]
