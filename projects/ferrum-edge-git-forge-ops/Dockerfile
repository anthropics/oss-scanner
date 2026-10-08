FROM ferrumedge/ferrum-edge:v0.9.15@sha256:29b468dfeea13b1ecaac8dfbc7e019f310e71e647611d43800a1dc64436eaca3 AS edge
FROM rust:1.99.0-bookworm@sha256:59037199c44290f2befcdd58dcc540164763fc296950255aaefeef096a1866b0 AS rust
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f

# Match the gateway binary's Debian runtime, while retaining the Rust toolchain.
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git curl bash python3 python3-yaml python3-jsonschema \
    build-essential pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=edge /app/ferrum-edge /usr/local/bin/ferrum-edge
COPY . /src
WORKDIR /src
ENV CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1

# Keep the validator binary and the full Rust/Python test environment offline.
RUN rustup toolchain install 1.99.0 --profile minimal \
    --component rustfmt --component clippy --component llvm-tools-preview \
    && cargo fetch --locked \
    && cargo build --locked \
    && cargo test --locked --no-run

CMD ["bash"]
