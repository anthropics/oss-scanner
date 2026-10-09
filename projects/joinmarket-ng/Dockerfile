# JoinMarket NG: a Python 3.14 monorepo (jmcore, jmwallet, jmwalletd, maker, taker, tumbler,
# directory_server, orderbook_watcher). Everything a scan needs offline is installed here: the locked
# runtime and dev dependencies of every component, the components themselves in editable mode, and a
# Bitcoin Core binary for local regtest reproductions.
FROM python:3.14-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# libsecp256k1 is loaded at runtime by python-bitcointx; libsodium and libffi back PyNaCl and cryptography
# when no wheel matches. whiptail, jq and shellcheck are used by the menu/install script tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git jq libffi-dev libsecp256k1-dev libsodium-dev \
      pkg-config shellcheck whiptail \
    && rm -rf /var/lib/apt/lists/*

# Bitcoin Core for regtest. The hashes are from https://bitcoincore.org/bin/bitcoin-core-31.1/SHA256SUMS.
ARG BITCOIN_VERSION=31.1
ARG BITCOIN_SHA256_AMD64=b80d9c3e04da78fb6f0569685673418cf686fadba9042d926d13fb87ff503f9e
ARG BITCOIN_SHA256_ARM64=dcf1873f2208ba4f962f3398d47e154c39c0084be8f4553e05c940d0ace3d004
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
      amd64) triple=x86_64-linux-gnu; sha="$BITCOIN_SHA256_AMD64" ;; \
      arm64) triple=aarch64-linux-gnu; sha="$BITCOIN_SHA256_ARM64" ;; \
      *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac; \
    tarball="bitcoin-${BITCOIN_VERSION}-${triple}.tar.gz"; \
    curl -fsSL --retry 3 -o "/tmp/$tarball" "https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/$tarball"; \
    echo "$sha  /tmp/$tarball" | sha256sum -c -; \
    tar -xzf "/tmp/$tarball" -C /tmp; \
    install -m 0755 "/tmp/bitcoin-${BITCOIN_VERSION}/bin/bitcoind" "/tmp/bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli" /usr/local/bin/; \
    rm -rf /tmp/bitcoin-*; \
    bitcoind -version | head -1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install the hash-locked dependency sets (runtime and dev) of every component in one resolution, then the
# components themselves as editable installs, so edits under /src take effect without reinstalling.
# The lock files omit setuptools (pip-tools needs it), so it is pinned here first, to the version the
# project's own Dockerfiles use.
ARG COMPONENTS="jmcore jmwallet jmwalletd directory_server orderbook_watcher maker taker tumbler"
RUN set -eu; \
    pip install setuptools==84.0.0 wheel==0.48.0; \
    reqs=""; \
    for c in $COMPONENTS; do reqs="$reqs -r $c/requirements.txt -r $c/requirements-dev.txt"; done; \
    pip install --require-hashes $reqs; \
    editable=""; \
    for c in $COMPONENTS; do editable="$editable -e ./$c"; done; \
    pip install --no-deps $editable; \
    pip check

# Regtest defaults matching the project's e2e setup (tests/e2e/conftest.py): user/password test/test,
# RPC on 127.0.0.1:18443. Start it with `bitcoind -daemon` inside the scan.
RUN mkdir -p /root/.bitcoin && printf '%s\n' \
      regtest=1 server=1 txindex=1 fallbackfee=0.0002 blockfilterindex=1 peerblockfilters=1 \
      '[regtest]' rpcuser=test rpcpassword=test rpcport=18443 rpcbind=127.0.0.1 rpcallowip=127.0.0.1 port=18444 \
      > /root/.bitcoin/bitcoin.conf

# Debuggers need ptrace; the daemons otherwise make themselves non-dumpable at startup.
ENV JOINMARKET_DISABLE_PROCESS_HARDENING=1

# Run the unit suites (the same two invocations as CI) so the image is known to work, without failing the
# build on a test failure. Docker-marked tests are excluded by pytest.ini, but a few e2e modules call
# `docker` at import time, so collection errors must not stop the rest of the repo-root suite. As root,
# the read-only directory tests in jmwallet/tests/test_utxo_metadata.py fail (root ignores permissions).
RUN (pytest -c pytest.ini -q -p no:cacheprovider --no-cov \
          jmcore jmwallet directory_server orderbook_watcher maker taker jmwalletd tumbler \
        || echo "WARNING: component unit tests reported failures") \
    && (pytest -c pytest.ini -q -p no:cacheprovider --no-cov tests --ignore=tests/playwright \
          --continue-on-collection-errors \
        || echo "WARNING: repo-root tests reported failures") \
    && git status --short
