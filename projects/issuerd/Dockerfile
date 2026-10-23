# OSS Scanner build image for Issuerd (https://github.com/issuerd/issuerd).
#
# Mirrors stage 1 of the repository's canonical production Dockerfile: same
# builder base (Microsoft Playwright image, chosen because it bundles Node and
# works where Docker Hub is restricted), same system packages, same pinned Rust
# toolchain. Single stage on purpose: the scanner installs its tool layer on
# top of this image and needs a package manager, so the distroless runtime
# stage of the production image is not used here.

FROM mcr.microsoft.com/playwright:v1.59.1-jammy

ENV DEBIAN_FRONTEND=noninteractive

# libkrb5-dev: Kerberos federation provider (libgssapi-sys). libclang-dev/clang:
# bindgen. libssl-dev/pkg-config: OpenSSL (webauthn-rs). sqlx is pure Rust, so
# no libpq is needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl build-essential libssl-dev pkg-config \
        libkrb5-dev libclang-dev clang \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain 1.95.0 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

COPY . /src
WORKDIR /src

# Embedded admin/account SPA. The generated SDK is gitignored, so it is rebuilt
# from the committed webclientsrc/openapi.json — same as the production build.
RUN cd webclientsrc && npm ci && npm run generate-api && npm run build

# Prove the toolchain works and leave the workspace fully compiled for offline
# analysis: unit tests (fast, no I/O; Docker-dependent suites skip gracefully),
# then a full workspace build so target/ holds every crate and the binary.
RUN cargo test --workspace --lib --locked
RUN cargo build --workspace --locked
