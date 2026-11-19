FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# Keep the source, development dependencies, and build outputs available offline.
COPY . /src
WORKDIR /src
RUN npm ci
RUN npm run build-all

CMD ["bash"]

