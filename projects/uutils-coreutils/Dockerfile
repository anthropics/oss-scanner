# syntax=docker/dockerfile:1
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential clang pkg-config \
      libacl1-dev libattr1-dev libselinux1-dev locales attr acl jq python3 \
    && rm -rf /var/lib/apt/lists/*

# Some integration tests need non-UTF-8 and non-Latin locales.
RUN printf '%s\n' 'en_US.UTF-8 UTF-8' 'fr_FR.UTF-8 UTF-8' 'ru_RU.KOI8-R KOI8-R' \
      'zh_CN.GB18030 GB18030' 'th_TH.UTF-8 UTF-8' 'fa_IR.UTF-8 UTF-8' 'am_ET.UTF-8 UTF-8' \
      > /etc/locale.gen && locale-gen

ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && chmod -R a+w "$RUSTUP_HOME" "$CARGO_HOME"

COPY . /src
WORKDIR /src

# Fetch every crate up front so later builds work offline.
RUN cargo fetch --locked

# Multicall binary at target/debug/coreutils, plus the integration test binary.
ENV RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo build --locked --features unix \
    && cargo test --locked --features unix --no-run

# Smoke test a few utilities; failures do not abort the build.
RUN (timeout 900 cargo test --locked --features unix -p coreutils -- \
        test_cat:: test_rm:: test_cp:: test_chmod:: \
     || echo "WARNING: uutils tests reported failures")
