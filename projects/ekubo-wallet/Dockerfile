# Ekubo Wallet: Rust workspace (GPUI desktop app, core crates, MCP bridge, erc8410).
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential pkg-config python3 clang cmake \
      libssl-dev libasound2-dev libfontconfig-dev libwayland-dev libx11-xcb-dev libxkbcommon-x11-dev \
      libxdo-dev libdbus-1-dev dbus gnome-keyring libvulkan-dev \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none

COPY . /src
WORKDIR /src

# rust-toolchain.toml selects the channel; vendor-free offline use needs everything fetched now.
RUN rustup show && cargo fetch --locked
RUN cargo build --locked --workspace --all-features --tests

RUN (timeout 1500 cargo test --locked --workspace --all-features --lib --offline || echo "WARNING: cargo test reported failures or timed out")
ENV CARGO_NET_OFFLINE=true
