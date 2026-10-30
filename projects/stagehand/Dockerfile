# Stagehand (https://github.com/browserbase/stagehand): a pnpm/turbo monorepo with a Chrome-extension runtime,
# a JSON-RPC protocol package, and TypeScript, Python, and Go SDKs. The build context is the repository root.
# Everything the audit needs (node_modules, the uv venv, Go modules, a Chrome binary) is fetched here, because the
# scan itself runs offline.
FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=1 \
    TURBO_TELEMETRY_DISABLED=1 \
    DO_NOT_TRACK=1 \
    PNPM_HOME=/usr/local/pnpm \
    GOTOOLCHAIN=local \
    PATH=/usr/local/pnpm:/usr/local/go/bin:/root/go/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Chrome for the browser-runtime tests and for exercising the SDKs' local launch path. Google ships Chrome for
# amd64 only; arm64 hosts (e.g. local `tools/check` on Apple silicon) get Debian's Chromium instead.
RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
      curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
      && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
           > /etc/apt/sources.list.d/google-chrome.list \
      && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
      && ln -sf /usr/bin/google-chrome-stable /usr/local/bin/chrome; \
    else \
      apt-get update && apt-get install -y --no-install-recommends chromium \
      && ln -sf /usr/bin/chromium /usr/local/bin/chrome; \
    fi \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_PATH=/usr/local/bin/chrome

# Toolchain versions match .github/workflows/ci.yml and the repo's devEngines.
RUN npm install -g pnpm@11.11.0
RUN curl -LsSf https://astral.sh/uv/0.11.29/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
RUN go_version="$(python3 -c "import json, urllib.request; print(next(r['version'] for r in json.load(urllib.request.urlopen('https://go.dev/dl/?mode=json')) if r['version'].startswith('go1.26')))")" \
    && curl -fsSL "https://go.dev/dl/${go_version}.linux-$(dpkg --print-architecture).tar.gz" | tar -C /usr/local -xz \
    && go version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# TypeScript: install and build every workspace package (protocol -> extension -> sdk-ts -> cli/integrations).
RUN pnpm install --frozen-lockfile
RUN pnpm build

# Python SDK: locked venv with dev deps, so pytest runs offline.
RUN cd packages/sdk-python && uv sync --locked --dev

# Go SDK: fetch modules and compile packages and tests so `go test` runs offline.
RUN cd packages/sdk-go && go mod download && go -C internal/generator mod download \
    && pkgs="$(go list ./... | grep -v '/examples$')" \
    && go build $pkgs && go test -count=1 -run '^$' $pkgs

# Smoke-check Chrome and run the cheap suites so the image is known-good; failures warn, they do not fail the build.
RUN "$CHROME_PATH" --headless=new --no-sandbox --disable-gpu --dump-dom about:blank >/dev/null \
    || echo "WARNING: Chrome failed to launch headless"
RUN pnpm test:unit || echo "WARNING: root unit tests reported failures"
RUN pnpm exec turbo run test:unit || echo "WARNING: package unit tests reported failures"
RUN pnpm exec turbo run test:browser || echo "WARNING: browser-runtime tests reported failures"
RUN cd packages/sdk-python && (uv run --locked pytest -q || echo "WARNING: Python SDK tests reported failures")
RUN cd packages/sdk-go && (go test $(go list ./... | grep -v '/examples$') || echo "WARNING: Go SDK tests reported failures")
