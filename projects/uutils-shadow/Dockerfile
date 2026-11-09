# syntax=docker/dockerfile:1
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive
# passwd, login and uidmap are the upstream shadow-utils tools, kept for comparison.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential clang pkg-config \
      libpam0g-dev libselinux1-dev libaudit-dev libcrypt-dev \
      passwd login uidmap locales \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' 'en_US.UTF-8 UTF-8' 'fr_FR.UTF-8 UTF-8' > /etc/locale.gen && locale-gen

# The PAM services and accounts the upstream test image provides.
RUN printf 'auth required pam_permit.so\naccount required pam_permit.so\npassword required pam_permit.so\nsession required pam_permit.so\n' > /etc/pam.d/shadow-rs-test-permit \
    && printf 'auth required pam_deny.so\naccount required pam_deny.so\npassword required pam_deny.so\nsession required pam_deny.so\n' > /etc/pam.d/shadow-rs-test-deny \
    && useradd -m -s /bin/bash testuser \
    && useradd -m -s /bin/sh testuser2 \
    && groupadd testgroup \
    && usermod -aG testgroup testuser

ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && chmod -R a+w "$RUSTUP_HOME" "$CARGO_HOME"

COPY . /src
WORKDIR /src

# Fetch every crate up front so later builds work offline.
RUN cargo fetch --locked

# Multicall binary at target/debug/shadow-rs, with PAM as in release builds.
ENV RUSTFLAGS="-C force-frame-pointers=yes"
RUN cargo build --locked --workspace --features pam \
    && cargo test --locked --workspace --features pam --no-run

# Smoke test; failures do not abort the build.
RUN (timeout 1200 cargo test --locked --workspace --features pam \
     || echo "WARNING: uutils shadow tests reported failures")
