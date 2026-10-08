FROM rust:1.99.0-bookworm@sha256:59037199c44290f2befcdd58dcc540164763fc296950255aaefeef096a1866b0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git bash python3 pkg-config libssl-dev libcurl4-openssl-dev \
    clang libclang-dev cmake mold protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Keep the compiler, registry cache, sources, and test executables for offline auditing.
# The repository's optional compiler cache is not needed in this standalone image.
ENV RUSTC_WRAPPER="" \
    CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=1 \
    CARGO_PROFILE_TEST_DEBUG=1
RUN rustup toolchain install stable --profile minimal --component rustfmt --component clippy \
    && cargo fetch --locked \
    && cargo build --locked --features cloud-secrets \
    && cargo test --locked --features cloud-secrets --no-run

CMD ["bash"]
