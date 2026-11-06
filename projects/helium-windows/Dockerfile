# helium-windows is a patch series and packaging on top of Helium's shared patches (the helium-chromium
# submodule), so this image holds the Chromium source with both series applied. The browser only builds on Windows
# and a full Chromium build does not fit in the scanner's build time limit, so nothing is compiled here.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      7zip ca-certificates curl git patch python3 ripgrep xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner does not clone submodules.
RUN git submodule update --init helium-chromium

# Same downloads as build.py --tarball, except for NSIS and portable Git, which are build tools: the base and
# Windows Chromium tarballs, WinSparkle, then deps.ini.
RUN mkdir -p /tmp/dl /chromium/src \
    && set -- -i helium-chromium/downloads.ini downloads.x64.ini -c /tmp/dl \
    && helium-chromium/utils/downloads.py retrieve "$@" \
    && helium-chromium/utils/downloads.py unpack "$@" /chromium/src \
    && set -- -i downloads.ini -c /tmp/dl --components=winsparkle \
    && helium-chromium/utils/downloads.py retrieve "$@" \
    && helium-chromium/utils/downloads.py unpack "$@" /chromium/src \
    && set -- -i helium-chromium/deps.ini -c /tmp/dl \
    && helium-chromium/utils/downloads.py retrieve "$@" \
    && helium-chromium/utils/downloads.py unpack "$@" /chromium/src \
    && rm -rf /tmp/dl

# Shared patches, then Windows patches, as build.py does. Domain and name substitution are skipped so that URLs
# and identifiers in the tree stay readable.
RUN helium-chromium/utils/prune_binaries.py --keep-build-dependencies /chromium/src helium-chromium/pruning.list \
    && helium-chromium/utils/patches.py apply /chromium/src helium-chromium/patches patches
