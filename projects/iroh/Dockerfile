# Scanner image for https://github.com/n0-computer/iroh (main): the iroh, iroh-base, iroh-relay, iroh-dns and
# iroh-dns-server crates.
#
# The audit runs offline, so this build fetches every crate in Cargo.lock, then builds the workspace with all features
# in the dev profile (debug assertions and overflow checks on): the libraries, the iroh-relay and iroh-dns-server
# binaries, the examples and every test binary. It also leaves a relay config with a self-signed certificate in
# /opt/iroh-local. threat_model.md, next to this file, says how to run all of it.

# Latest stable Rust, which is what the repository's CI tests with.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive
# .cargo/config.toml links x86_64 Linux targets with clang and lld. aws-lc-sys builds with cmake. dig queries the DNS
# server. ip, tc, nft, ping and conntrack are what the patchbay NAT labs (iroh/tests/patchbay.rs) drive.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang lld cmake bind9-dnsutils iproute2 nftables iputils-ping conntrack \
    && rm -rf /var/lib/apt/lists/*

# cargo-nextest, at the version CI pins: the repository's .config/nextest.toml bounds slow tests and leaves out the
# patchbay network-namespace tests by default.
ARG NEXTEST_VERSION=0.9.80
RUN case "$(uname -m)" in x86_64) platform=linux ;; aarch64) platform=linux-arm ;; *) exit 1 ;; esac \
    && curl -fsSL "https://get.nexte.st/${NEXTEST_VERSION}/${platform}" | tar -xzf - -C "${CARGO_HOME}/bin" \
    && cargo nextest --version

# A relay config for local testing: the relay over HTTPS on 127.0.0.1:3443 and QUIC address discovery on 127.0.0.1:7842,
# with a self-signed certificate for localhost. Plain HTTP on 127.0.0.1:3340 then serves only the captive-portal check.
RUN mkdir -p /opt/iroh-local \
    && openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 3650 -subj /CN=localhost \
         -addext subjectAltName=DNS:localhost,IP:127.0.0.1 \
         -keyout /opt/iroh-local/relay.key -out /opt/iroh-local/relay.crt \
    && printf '%s\n' \
         'http_bind_addr = "127.0.0.1:3340"' \
         'enable_quic_addr_discovery = true' \
         'enable_metrics = false' \
         '' \
         '[tls]' \
         'https_bind_addr = "127.0.0.1:3443"' \
         'quic_bind_addr = "127.0.0.1:7842"' \
         'cert_mode = "Manual"' \
         'manual_cert_path = "/opt/iroh-local/relay.crt"' \
         'manual_key_path = "/opt/iroh-local/relay.key"' \
         > /opt/iroh-local/relay.toml

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never

# Every crate in Cargo.lock, for every target and feature, so later builds with other features or cfgs stay offline.
RUN cargo fetch --locked

# The workspace with all features, as CI's "all features" cell builds it: libraries, binaries, examples and every test
# binary. A step that fails fails the build, and primary_contact gets the log.
RUN cargo build --locked --workspace --all-features --lib --bins --examples \
    && cargo nextest run --locked --workspace --all-features --lib --bins --tests --no-run

# Run the tests so the log shows the image works, without letting a failure (or a test that needs the Internet) abort
# the build.
RUN timeout 900 cargo nextest run --locked --workspace --all-features --lib --bins --tests --no-fail-fast \
    || echo "WARNING: cargo nextest reported failures"

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
