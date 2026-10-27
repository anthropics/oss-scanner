FROM rust:1-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang cmake git libssl-dev pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies the ureq checkout as the build context.
COPY . /src
WORKDIR /src

ARG CARGO_BUILD_JOBS=4
RUN cargo fetch --locked

ENV CARGO_NET_OFFLINE=true \
    RUSTFLAGS="-C force-frame-pointers=yes"

# Compile the real transports and examples without the internal _test feature.
RUN cargo build --locked --all-targets \
      --features native-tls,platform-verifier,socks-proxy,cookies,brotli,charset,json,multipart

# _test uses the repository's mock transport, making the full suite work offline.
RUN cargo test --locked --all-features

# Exercise real socket and TLS I/O against loopback peers without _test.
RUN cargo test --locked --no-default-features --features native-tls --test native_tls \
    && cargo test --locked --no-default-features --features native-tls-no-default --test native_tls \
    && cargo test --locked --no-default-features --test tcp_eintr
