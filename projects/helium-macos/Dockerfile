# helium-macos is a patch series and packaging on top of Helium's shared patches (the helium-chromium submodule),
# so this image holds the Chromium source with both series applied. The browser only builds on macOS and a full
# Chromium build does not fit in the scanner's build time limit, so nothing is compiled here.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git patch python3 ripgrep xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner does not clone submodules.
RUN git submodule update --init helium-chromium

# Same flow as fetch_sources in devutils/shared.sh on an x86_64 host: the base and macOS Chromium tarballs,
# Sparkle, then deps.ini.
RUN mkdir -p /tmp/dl /chromium/src \
    && set -- -i helium-chromium/downloads.ini downloads.x64.ini downloads.ini helium-chromium/deps.ini \
    && helium-chromium/utils/downloads.py retrieve "$@" -c /tmp/dl \
    && helium-chromium/utils/downloads.py unpack "$@" -c /tmp/dl /chromium/src \
    && rm -rf /tmp/dl

# Shared patches, then macOS patches, as prepare_sources does. Domain and name substitution are skipped so that
# URLs and identifiers in the tree stay readable.
RUN helium-chromium/utils/prune_binaries.py --keep-build-dependencies /chromium/src helium-chromium/pruning.list \
    && helium-chromium/utils/patches.py apply /chromium/src helium-chromium/patches patches
