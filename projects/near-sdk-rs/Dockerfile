FROM rust:1.95-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_BUILD_JOBS=2 \
    RUST_TEST_THREADS=2 \
    RUST_BACKTRACE=1 \
    INSTA_UPDATE=no \
    NEAR_SANDBOX_BIN_PATH=/opt/near-sandbox/near-sandbox

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang llvm libclang-dev cmake pkg-config libssl-dev libudev-dev \
      protobuf-compiler python3 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rustup component add rustfmt \
    && rustup target add wasm32-unknown-unknown

# Match the CLI and sandbox versions used by the repository's test workflows.
RUN curl --proto '=https' --tlsv1.2 -fsSL \
      https://github.com/near/cargo-near/releases/download/cargo-near-v0.21.0/cargo-near-installer.sh \
      -o /tmp/cargo-near-installer.sh \
    && sh /tmp/cargo-near-installer.sh \
    && rm /tmp/cargo-near-installer.sh \
    && cargo near --version
RUN mkdir -p /opt/near-sandbox \
    && curl --proto '=https' --tlsv1.2 -fsSL \
      "https://s3-us-west-1.amazonaws.com/build.nearprotocol.com/nearcore/Linux-$(uname -m)/2.14.0-rc.2/near-sandbox.tar.gz" \
      -o /tmp/near-sandbox.tar.gz \
    && tar -xzf /tmp/near-sandbox.tar.gz --strip-components=1 -C /opt/near-sandbox \
    && rm /tmp/near-sandbox.tar.gz \
    && "$NEAR_SANDBOX_BIN_PATH" --version

# Keep the physical workspace distinct from Cargo's registry/src paths so
# trybuild can normalize diagnostics correctly. The scanner still uses /src.
COPY . /work/near-sdk-rs
RUN ln -s /work/near-sdk-rs /src
WORKDIR /work/near-sdk-rs

# Examples are separate workspaces. Cache their dependencies as well as the
# workspace and the contracts compiled dynamically by integration tests.
RUN cargo fetch \
    && find examples near-sdk/tests/test-contracts -name Cargo.toml \
      -exec sh -ec 'for manifest do cargo fetch --manifest-path "$manifest"; done' sh '{}' +

# Running the suite online also warms cargo-near's generated ABI build inputs
# and the contract artifacts required by sandbox-backed tests.
RUN cargo test --workspace --features unstable,legacy,__abi-generate,deterministic-account-ids

ENV CARGO_NET_OFFLINE=true
