# OSS Scanner build of PDF.js.
#
# The scanner builds this with the pdf.js checkout as the build context, so `COPY . /src` puts it at /src.
# Network access exists only while this file builds, so everything the tests need is fetched here: the npm
# dependencies, the PDFs referenced by test/pdfs/*.link, and a Firefox Nightly for puppeteer.
#
# What is built:
#   build/generic/         the library and the generic viewer, as published (served by `npx gulp server`)
#   build/generic-legacy/  and build/lib-legacy/: the TESTING builds made by `npx gulp unittestcli`
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PUPPETEER_CACHE_DIR=/opt/puppeteer

# firefox-esr is installed for the shared libraries the puppeteer-managed Firefox Nightly needs. xvfb is for the
# integration tests, which upstream runs in a headful browser.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 firefox-esr xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN npm ci
RUN npx puppeteer browsers install firefox@nightly
RUN npx gulp generic

# Same steps as CI (.github/workflows/ci.yml). Linked PDFs live on third-party hosts and some may be gone, so
# neither step fails the build.
RUN (cd test && node test.mjs --downloadOnly) || echo "WARNING: some linked test PDFs could not be downloaded"
RUN npx gulp unittestcli || echo "WARNING: CLI unit tests reported failures"
