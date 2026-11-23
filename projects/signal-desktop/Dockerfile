# Signal-Desktop (https://github.com/signalapp/Signal-Desktop), Signal's Electron app for Windows, macOS and Linux.
#
# Set up the way CI's Linux job sets up for `test-node`: install with pnpm, install Electron's binary, then
# `pnpm run generate`. The app is not packaged (no electron-builder release build); the scanner works on the source.
# Node and pnpm follow the versions the repository pins (.nvmrc and devEngines). The native modules (libsignal-client,
# ringrtc, sqlcipher) come prebuilt from npm, so, as in CI, node-gyp compiles nothing.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
# Electron's runtime libraries, and xvfb, because even `pnpm run test-node` runs inside Electron (electron-mocha).
# libpulse0 is in CI's apt list for the same job.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils python3 \
      libgtk-3-0 libnss3 libasound2 libgbm1 libxss1 libxtst6 libpulse0 xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the scanner builds this Dockerfile with the Signal-Desktop checkout as the build context, and the
# checkout must live inside the image, at /src. The checkout includes .git, which `generate` uses for the build time.
COPY . /src
WORKDIR /src

# The exact Node that .nvmrc names (it changes often, so it is read rather than pinned here), sha256 checked against
# nodejs.org's SHASUMS256.txt, over the base image's Node 24. Then the pnpm that devEngines names.
RUN NODE_VERSION="$(cat .nvmrc | tr -d 'v[:space:]')" \
    && cd /tmp \
    && curl --proto '=https' --tlsv1.2 -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && curl --proto '=https' --tlsv1.2 -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" \
         | grep " node-v${NODE_VERSION}-linux-x64.tar.xz\$" | sha256sum -c - \
    && tar -xJf "node-v${NODE_VERSION}-linux-x64.tar.xz" -C /usr/local --strip-components=1 --no-same-owner \
    && rm "node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && cd /src \
    && npm install --global "pnpm@$(node -p 'require("./package.json").devEngines.packageManager.version')" \
    && node --version && pnpm --version

# Install as CI does. npm_config_node_gyp=echo keeps node-gyp from compiling anything; the native modules are prebuilt.
# Electron downloads its binary the first time it runs, which the scan cannot do, so install-electron fetches it now.
RUN npm_config_node_gyp=echo pnpm install --frozen-lockfile \
    && ./node_modules/.bin/install-electron

# Protobufs, emoji data, the bundle, styles and locales, as CI runs before its tests.
RUN pnpm run generate

# The scan has no network. The scanner runs as root, and Chromium refuses to start as root with its sandbox on.
ENV npm_config_offline=true \
    ELECTRON_DISABLE_SANDBOX=1
