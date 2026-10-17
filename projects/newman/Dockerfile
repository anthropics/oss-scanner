# Install dependencies while network access is available. Node 22 is inside the
# range that CI tests (18.x and latest).
FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PUPPETEER_SKIP_DOWNLOAD=true \
    CI=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN npm ci

# Browser and network-backed tests cannot run offline, so only unit tests run
# here. A failing test does not fail the build.
RUN npm run test-unit || echo "WARNING: unit tests reported failures"

CMD ["bash"]
