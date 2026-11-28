# MCP Apps SDK, built and tested the way its CI (.github/workflows/ci.yml) does: npm ci (which also builds the library,
# through "prepare"), the examples, then bun's test runner. Bun itself is a development dependency in package.json.
FROM node:22-bookworm

ENV CI=true \
    HUSKY=0 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci
RUN npm run build
RUN npm run examples:build

# A headless browser, so that the iframe sandbox in examples/basic-host can be exercised for real. Not needed by the
# unit tests, so a failed download must not abort the build.
RUN npx playwright install --with-deps --only-shell chromium || echo "WARNING: no browser installed"

# There is no network when the scanner runs: dependencies are used as installed above.
ENV npm_config_offline=true

# A failing test must not abort the image build.
RUN timeout 900 npm test || echo "WARNING: tests reported failures"
