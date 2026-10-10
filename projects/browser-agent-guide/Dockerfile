FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Pre-install dependencies so full offline access is available during scanning
RUN npm ci --ignore-scripts || npm install

# Pre-run baseline syntax validation and unit tests
RUN npm run check:js
RUN node test/slug.test.mjs && \
    node test/recipe-merge.test.mjs && \
    node test/prompt.test.mjs && \
    node test/workflow-lib.test.mjs || echo "WARNING: unit tests had non-zero exit during image build"
