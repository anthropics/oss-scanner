# Bitcoin Safe / Anthropic OSS Scanner: Python 3.12, CBF backend, Bitcoin Core 32.1.
# This Dockerfile lives next to projects/bitcoin-safe/project.yaml in the
# anthropics/oss-scanner repo. Anthropic builds using Bitcoin Safe as the context.
# Image is for Linux x86_64; builds run with network, scans run without network.
FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    QT_QPA_PLATFORM=offscreen \
    XDG_RUNTIME_DIR=/tmp/bitcoin-safe-runtime \
    PATH=/src/.venv/bin:$PATH

# Qt/Xvfb dependencies track .github/workflows/python-tests.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget git build-essential pkg-config cmake clang \
      libssl-dev libffi-dev libgpgme-dev \
      libzbar0 libzbar-dev \
      libusb-1.0-0 libusb-1.0-0-dev \
      libhidapi-hidraw0 libhidapi-libusb0 \
      libglib2.0-0 libdbus-1-3 \
      libgl1 libegl1 libopengl0 libglu1-mesa \
      libxkbcommon0 libxkbcommon-dev libxkbcommon-x11-0 libxkbcommon-x11-dev \
      libx11-xcb1 libx11-xcb-dev libxrender1 libxrender-dev libxi6 libxi-dev \
      libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
      libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinput0 \
      libxcb-xfixes0 libxcb-shape0 libxcb-xkb1 libxcb-sync1 libxcb-shm0 \
      libpulse0 fonts-dejavu-core xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Install project and dev dependencies online so pytest runs offline.
RUN python -m pip install --no-cache-dir 'poetry==2.5.1' \
    && poetry install --only main,dev --no-interaction --no-ansi \
    && mkdir -p "$XDG_RUNTIME_DIR" \
    && chmod 700 "$XDG_RUNTIME_DIR"

# Bitcoin Safe's tests/setup_bitcoin_core.py is pinned to 29.2 upstream.
# Patch only the scanner's temporary checkout (NOT the GitHub repository)
# to load 32.1, otherwise its fixture tries to download 29.2 offline.
# Pin the 32.1 release digest to the Guix build attestation published by
# bitcoin-core/guix.sigs (32.1/fanquake/all.SHA256SUMS).
# curl exit code 18 = truncated response; continue each partial download
# using HTTP Range, then fall back to wget --continue for slow/CDN networks.
RUN set -eux; \
    test "$(uname -m)" = 'x86_64'; \
    sed -i 's/^BITCOIN_VERSION = "29\.2"$/BITCOIN_VERSION = "32.1"/' tests/setup_bitcoin_core.py; \
    grep -Fx 'BITCOIN_VERSION = "32.1"' tests/setup_bitcoin_core.py; \
    mkdir -p tests/bitcoin_core; \
    cd tests/bitcoin_core; \
    archive='bitcoin-32.1-x86_64-linux-gnu.tar.gz'; \
    url="https://bitcoincore.org/bin/bitcoin-core-32.1/$archive"; \
    complete=0; \
    for attempt in 1 2 3 4 5 6 7 8; do \
      if curl --http1.1 --fail --location --silent --show-error \
            --connect-timeout 30 --max-time 150 --continue-at - \
            --output "$archive" "$url"; then complete=1; break; fi; \
      echo "Bitcoin Core 32.1 download incomplete; resuming, attempt $attempt/8" >&2; \
      sleep 3; \
    done; \
    if [ "$complete" -ne 1 ]; then \
      echo 'curl retries exhausted; switching to wget --continue' >&2; \
      wget --continue --tries=5 --timeout=60 --waitretry=3 \
           --output-document="$archive" "$url"; \
    fi; \
    echo '61545c17c3120fb7412f896d248b11993af04ec8817aad3649c55b2afb044963  bitcoin-32.1-x86_64-linux-gnu.tar.gz' | sha256sum -c -; \
    tar -xzf "$archive"; \
    test -x bitcoin-32.1/bin/bitcoind; \
    test -x bitcoin-32.1/bin/bitcoin-cli; \
    printf '%s\n' "$archive" > .artifact_name; \
    bitcoin-32.1/bin/bitcoind -version

# Smoke tests work without an external Bitcoin network or Fulcrum.
RUN python -m compileall -q bitcoin_safe tests \
    && python -c 'import bitcoin_safe; import bdkpython; from PyQt6 import QtCore; print("Bitcoin Safe/BDK/Qt imports OK", QtCore.QT_VERSION_STR)' \
    && pytest --cbf -q -m 'not integration' --maxfail=1 tests/non_gui/test_cbf_sync.py

# Offline, e.g. after tools/check bitcoin-safe:
#   pytest --cbf -q -m 'not integration' --maxfail=1 tests/setup_bitcoin_core.py
#   QT_QPA_PLATFORM=xcb xvfb-run -a -s '-screen 0 1920x1200x24' \
#     pytest --cbf -q -m 'not integration' --maxfail=1 tests/non_gui/
# Some tests need hardware, external services, or mainnet; exercise only local
# regtest with synthetic wallet data (public mnemonic: bacon x 24).
CMD ["bash"]
