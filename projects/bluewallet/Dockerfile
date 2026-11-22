# BlueWallet is a React Native app. This image prepares the JavaScript/TypeScript side only: dependencies, the
# TypeScript check and the jest unit tests. No Android or iOS native build is done.
FROM node:22-bookworm

ENV CI=true \
    NODE_OPTIONS=--max-old-space-size=8192 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

COPY . /src
WORKDIR /src

# postinstall writes release-notes.json and current-branch.json from git history, then applies patches/ with
# patch-package. Some packages fetch prebuilt binaries during install, so retry once on a network hiccup.
RUN git config --global --add safe.directory /src \
    && (npm ci || npm ci)

RUN npx tsc

# Unit tests are offline (tests/unit). Integration tests (tests/integration) need live Electrum/HTTP servers,
# and e2e tests need a device, so neither is run. A failing test does not fail the build.
RUN printf '#!/usr/bin/env bash\ncd /src\nexec npx jest tests/unit/ "$@"\n' > /usr/local/bin/bluewallet-oss-test \
    && chmod +x /usr/local/bin/bluewallet-oss-test
RUN bluewallet-oss-test --maxWorkers=4 || echo "WARNING: jest unit tests reported failures"

CMD ["bash"]
