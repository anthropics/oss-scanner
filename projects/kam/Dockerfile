FROM rust:1.96-trixie
ENV CARGO_BUILD_JOBS=2 \
    RUSTFLAGS="-C debuginfo=1 -C force-frame-pointers=yes"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config libssl-dev cmake clang libclang-dev \
      protobuf-compiler libfuse3-dev python3 unzip zip jq \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
RUN cargo fetch --locked && cargo build --locked --workspace && cargo test --locked --workspace --no-run
