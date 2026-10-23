# The scanner supplies a clean public RisingWave checkout as the build context.
# Based on RisingWave's ci/Dockerfile and docker/Dockerfile; no host credentials
# or production configuration are needed. Sources and caches stay in the image.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    CC=clang \
    CXX=clang++ \
    LIBCLANG_PATH=/usr/lib/llvm-18/lib \
    PYO3_PYTHON=/usr/bin/python3.12 \
    CARGO_INCREMENTAL=0 \
    CARGO_BUILD_JOBS=16 \
    CMAKE_BUILD_PARALLEL_LEVEL=16 \
    ENABLE_BUILD_DASHBOARD=0 \
    ENABLE_TELEMETRY=false \
    AWS_EC2_METADATA_DISABLED=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential clang libclang-dev lld cmake \
      ninja-build pkg-config protobuf-compiler libprotobuf-dev libssl-dev libsasl2-dev \
      libkrb5-dev libcurl4-openssl-dev libzstd-dev zlib1g-dev liblzma-dev \
      libblas-dev liblapack-dev libomp-dev openjdk-21-jdk-headless \
      python3 python3.12-dev postgresql-client procps gdb file unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --profile minimal --default-toolchain none \
    && rm /tmp/rustup-init.sh
ENV PATH=/root/.cargo/bin:$PATH

# Scanner contract: preserve the checkout at /src.
COPY . /src
WORKDIR /src

# Prefer fast cold builds on the smaller enrollment CI runner. Keep line tables,
# debug assertions and overflow checks; only dependency optimization is disabled.
# Cargo config overrides the manifest's ci-dev dependency opt-levels (1 / 3).
RUN printf '\n%s\n' \
      '[profile.ci-dev.package."*"]' 'opt-level = 0' \
      '[profile.ci-dev.package.tokio]' 'opt-level = 0' \
      '[profile.ci-dev.package.await-tree]' 'opt-level = 0' \
      '[profile.ci-dev.package.indextree]' 'opt-level = 0' \
      >> /src/.cargo/config.toml

# The root rust-toolchain is a symlink to ci/rust-toolchain. Follow the version
# selected by the public checkout rather than pinning a second nightly here.
RUN rustup set auto-self-update disable && rustup toolchain install --profile minimal \
    && rustup component add rustfmt rust-src \
    && rustup target add wasm32-wasip1

# Fetch public Rust dependencies while the build has network access. Use the
# lockfile and retain registry/git caches so the scanner can rebuild offline.
# Retry transient TLS failures within this layer, retaining downloaded objects.
RUN export CARGO_NET_GIT_FETCH_WITH_CLI=true GIT_TERMINAL_PROMPT=0; \
    for attempt in 1 2 3; do \
      timeout 300 cargo fetch --locked && exit 0; \
    done; \
    exit 1

# Skip the heavy optional LanceDB sink and frontend DataFusion feature. Connector
# dependencies can still compile DataFusion. Lite sinks and embedded UDFs are enabled;
# Java connector assemblies and the dashboard UI are not built (see threat model).
# Keep the test feature graph aligned with the binary to reuse compiled dependencies.
RUN cargo build --locked --profile ci-dev -p risingwave_cmd_all \
      --no-default-features --features rw-dynamic-link,all-connectors-lite,udf \
    && cargo test --locked --profile ci-dev --no-run --lib \
      -p risingwave_cmd_all -p risingwave_sqlparser -p pgwire -p risingwave_connector_codec \
      --no-default-features \
      --features risingwave_cmd_all/rw-dynamic-link,risingwave_cmd_all/all-connectors-lite,risingwave_cmd_all/udf

# Use the small audit machine defaults after the online build is complete.
# A successful build must leave the program runnable and the small unit suites
# executable without downloading anything. Fail instead of masking test failures.
ENV CARGO_NET_OFFLINE=true \
    CARGO_BUILD_JOBS=2 \
    CMAKE_BUILD_PARALLEL_LEVEL=2
RUN /src/target/ci-dev/risingwave --version \
    && cargo test --locked --offline --profile ci-dev --lib \
      -p risingwave_cmd_all -p risingwave_sqlparser -p pgwire -p risingwave_connector_codec \
      --no-default-features \
      --features risingwave_cmd_all/rw-dynamic-link,risingwave_cmd_all/all-connectors-lite,risingwave_cmd_all/udf

CMD ["bash"]
