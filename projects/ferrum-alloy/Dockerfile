FROM rust:1.99.0-bookworm@sha256:59037199c44290f2befcdd58dcc540164763fc296950255aaefeef096a1866b0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git bash python3 pkg-config libssl-dev clang libclang-dev cmake \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
ENV CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1

# Install the repository's pinned compiler and precompile every workspace feature.
RUN rustup toolchain install 1.98.1 --profile minimal --component rustfmt --component clippy \
    && cargo fetch --locked \
    && cargo build --locked --workspace --all-features \
    && cargo test --locked --workspace --all-features --no-run

CMD ["bash"]
