FROM node:22-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates git python3 ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Keep the source, development dependencies, and build outputs available offline.
COPY . /src
WORKDIR /src
RUN npm ci
RUN npx playwright install --with-deps chromium
RUN npm run build:server && npm run build:web --workspace=@getpaseo/app

CMD ["bash"]
