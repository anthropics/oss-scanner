FROM rust:1.95-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_BUILD_JOBS=2 \
    RUST_BACKTRACE=1 \
    INSTA_UPDATE=no

RUN apt-get update && apt-get install -y --no-install-recommends \
      clang llvm libclang-dev pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Resolve and retain dependencies for the complete workspace, then build and run
# the project's CI matrix (std/no_std, derives, schema and optional integrations).
# Do not use --all-features: force_exhaustive_checks is a nightly-only CI check.
RUN cargo fetch && bash .github/test.sh

ENV CARGO_NET_OFFLINE=true
