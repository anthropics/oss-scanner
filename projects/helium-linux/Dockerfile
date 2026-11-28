# helium-linux is a patch series and packaging on top of Helium's shared patches (the helium-chromium submodule),
# so this image holds the Chromium source with both series applied. A full Chromium build does not fit in the
# scanner's build time limit, so nothing is compiled here; the latest release is installed instead for reproducing
# findings at runtime.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq patch python3 ripgrep xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner does not clone submodules.
RUN git submodule update --init helium-chromium

# Same flow as fetch_sources in scripts/shared.sh: the base and Linux Chromium tarballs, then deps.ini.
RUN mkdir -p /tmp/dl /chromium/src \
    && helium-chromium/utils/downloads.py retrieve -i helium-chromium/downloads.ini downloads.ini -c /tmp/dl \
    && helium-chromium/utils/downloads.py unpack -i helium-chromium/downloads.ini downloads.ini -c /tmp/dl /chromium/src \
    && helium-chromium/utils/downloads.py retrieve -i helium-chromium/deps.ini -c /tmp/dl \
    && helium-chromium/utils/downloads.py unpack -i helium-chromium/deps.ini -c /tmp/dl /chromium/src \
    && rm -rf /tmp/dl

# Shared patches, then Linux patches, as apply_patches does. Domain and name substitution are skipped so that URLs
# and identifiers in the tree stay readable.
RUN helium-chromium/utils/prune_binaries.py --keep-build-dependencies /chromium/src helium-chromium/pruning.list \
    && helium-chromium/utils/patches.py apply /chromium/src helium-chromium/patches patches

# Latest release, for running reproducers (e.g. helium --headless --no-sandbox). It may trail main.
RUN url="$(curl -fsSL https://api.github.com/repos/imputnet/helium-linux/releases/latest \
        | jq -r '.assets[].browser_download_url | select(test("helium-bin_.*_amd64\\.deb$"))')" \
    && curl -fsSL -o /tmp/helium.deb "$url" \
    && apt-get update && apt-get install -y --no-install-recommends /tmp/helium.deb \
    && rm -rf /tmp/helium.deb /var/lib/apt/lists/* \
    && (helium --headless --no-sandbox --dump-dom about:blank || echo "WARNING: helium failed to start")
