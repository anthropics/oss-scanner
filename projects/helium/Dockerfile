# Helium is a patch series on top of Chromium, so this image holds the Chromium source for the version in
# chromium_version.txt with Helium's patches applied. A full Chromium build does not fit in the scanner's build
# time limit, so nothing is compiled here; the latest Linux release of Helium is installed instead for
# reproducing findings at runtime.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq patch python3 ripgrep xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Prepared Chromium source tarball plus the extra components from deps.ini, unpacked to /chromium/src. This is
# the same flow as fetch_sources in helium-linux/scripts/shared.sh, minus the platform tarball.
RUN mkdir -p /tmp/dl /chromium/src \
    && utils/downloads.py retrieve -i downloads.ini -c /tmp/dl \
    && utils/downloads.py unpack -i downloads.ini -c /tmp/dl /chromium/src \
    && utils/downloads.py retrieve -i deps.ini -c /tmp/dl \
    && utils/downloads.py unpack -i deps.ini -c /tmp/dl /chromium/src \
    && rm -rf /tmp/dl

# Apply Helium's shared patch series, as apply_patches does. Domain and name substitution are skipped so that
# URLs and identifiers in the tree stay readable.
RUN utils/prune_binaries.py --keep-build-dependencies /chromium/src pruning.list \
    && utils/patches.py apply /chromium/src patches

# Latest Linux release, for running reproducers (e.g. helium --headless --no-sandbox). It may trail main by a
# Chromium milestone.
RUN url="$(curl -fsSL https://api.github.com/repos/imputnet/helium-linux/releases/latest \
        | jq -r '.assets[].browser_download_url | select(test("helium-bin_.*_amd64\\.deb$"))')" \
    && curl -fsSL -o /tmp/helium.deb "$url" \
    && apt-get update && apt-get install -y --no-install-recommends /tmp/helium.deb \
    && rm -rf /tmp/helium.deb /var/lib/apt/lists/* \
    && (helium --headless --no-sandbox --dump-dom about:blank || echo "WARNING: helium failed to start")
