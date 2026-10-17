# syntax=docker/dockerfile:1

# Based on Juspay Hyperswitch's official Dockerfile.
FROM public.ecr.aws/docker/library/rust:trixie

ARG EXTRA_FEATURES="--features redis-rs"
ARG VERSION_FEATURE_SET="v1"
ARG CARGO_BUILD_PROFILE=dev

ENV CARGO_BUILD_JOBS=8
ENV CARGO_PROFILE_DEV_DEBUG=0
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_INCREMENTAL=0 \
    CARGO_NET_RETRY=10 \
    RUSTUP_MAX_RETRIES=10 \
    RUST_BACKTRACE=short

# Same native dependencies as the official Dockerfile,
# plus libprotobuf-dev to resolve the scanner build error.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      curl \
      build-essential \
      libpq-dev \
      libssl-dev \
      pkg-config \
      protobuf-compiler \
      libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

# Anthropic requires the complete source tree.
COPY . /src
WORKDIR /src

# Fetch dependencies for subsequent offline analysis.
RUN cargo fetch --locked

# Preserve Hyperswitch's official feature selection and
# build command. Only use a development build profile
# to retain debug information and avoid production LTO.
RUN cargo build \
    --profile ${CARGO_BUILD_PROFILE} \
    --no-default-features \
    --features release \
    --features ${VERSION_FEATURE_SET} \
    ${EXTRA_FEATURES}

# Keep source code, toolchain, dependencies, and binaries
# available for Anthropic's offline scanner.
CMD ["/bin/bash"]
