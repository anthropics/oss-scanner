# Scanner image for https://github.com/stratum-mining/sv2-apps.
#
# The audit runs offline, so this build installs the toolchain, fetches every crate, downloads the external
# binaries the integration tests drive (Bitcoin Core, sv2-tp, minerd), and compiles the workspace and its tests.
# threat_model.md, next to this file, says how to run each of them.

# The repository pins its toolchain in rust-toolchain.toml (1.88.0); installing it needs the network, so that happens here.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# capnproto and libcapnp-dev compile the Bitcoin Core IPC schemas that bitcoin-core-sv2's bitcoin-capnp-types
# dependencies build, as the repository's CI installs them. python3 is for ad-hoc scripts.
RUN apt-get update && apt-get install -y --no-install-recommends capnproto libcapnp-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# The pinned toolchain plus the components rust-toolchain.toml asks for, and every crate the workspace depends on.
RUN rustup toolchain install && cargo fetch

# The workspace and its tests, including the integration test crate, in one pass (CI builds crate by crate, which the
# test step below reproduces). A step that fails fails the build, and primary_contact gets the log.
RUN cargo build --workspace && cargo test --workspace --no-run

# The binaries the integration tests download on first use, at the versions integration-tests/lib pins
# (BITCOIN_CORE_V30X, BITCOIN_CORE_V31X, VERSION_SV2_TP, VERSION_MINERD), unpacked where the tests look for them, for
# the architecture this image is built on (the scanner's is x86-64). The Bitcoin Core tarballs are checked against the
# release's SHA256SUMS; the sv2-tp and cpuminer releases ship no checksum file, and the tests themselves verify none.
# tar detects the compression itself: the arm64 cpuminer release is a plain tar despite its .tar.gz name.
ARG BITCOIN_CORE_VERSIONS="30.2 31.0"
ARG SV2_TP_VERSION=1.1.0
ARG MINERD_VERSION=2.5.1
RUN set -e; case "$(uname -m)" in \
      x86_64)  gnu=x86_64-linux-gnu;  minerd=linux-x86_64 ;; \
      aarch64) gnu=aarch64-linux-gnu; minerd=linux-arm64 ;; \
      *) echo "unsupported architecture $(uname -m)"; exit 1 ;; \
    esac \
    && cd integration-tests && mkdir -p template-provider minerd \
    && for v in $BITCOIN_CORE_VERSIONS; do \
         f="bitcoin-$v-$gnu.tar.gz" \
         && curl -fsSL -o "/tmp/$f" "https://bitcoincore.org/bin/bitcoin-core-$v/$f" \
         && curl -fsSL "https://bitcoincore.org/bin/bitcoin-core-$v/SHA256SUMS" | grep " $f\$" | (cd /tmp && sha256sum -c -) \
         && tar -xzf "/tmp/$f" -C template-provider && rm "/tmp/$f" \
         && test -x "template-provider/bitcoin-$v/libexec/bitcoin-node" || exit 1; \
       done \
    && curl -fsSL -o /tmp/sv2-tp.tar.gz "https://github.com/stratum-mining/sv2-tp/releases/download/v$SV2_TP_VERSION/sv2-tp-$SV2_TP_VERSION-$gnu.tar.gz" \
    && tar -xf /tmp/sv2-tp.tar.gz -C template-provider && rm /tmp/sv2-tp.tar.gz \
    && test -x "template-provider/sv2-tp-$SV2_TP_VERSION/bin/sv2-tp" \
    && curl -fsSL -o /tmp/minerd.tar.gz "https://github.com/stratum-mining/cpuminer/releases/download/v$MINERD_VERSION/pooler-cpuminer-$MINERD_VERSION-$minerd.tar.gz" \
    && tar -xf /tmp/minerd.tar.gz -C minerd && rm /tmp/minerd.tar.gz \
    && test -x minerd/minerd

# Run the unit tests crate by crate, as CI does (a workspace-wide run would unify stratum-apps features across the
# apps), plus one integration test to show the external binaries work, without letting a failure abort the build.
RUN (timeout 900 sh -c 'cargo test -p stratum-apps --all-features && cargo test -p pool_sv2 && cargo test -p jd_server_sv2 \
        && cargo test -p jd_client_sv2 && cargo test -p translator_sv2 && cargo test -p bitcoin_core_sv2' \
     || echo "WARNING: cargo test reported failures") \
    && (timeout 600 cargo test -p integration_tests_sv2 --test pool_integration \
     || echo "WARNING: the integration test reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
