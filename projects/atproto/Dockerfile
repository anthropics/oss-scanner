FROM node:24-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates build-essential git python3 pkg-config \
        postgresql postgresql-client redis-server chromium \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

COPY . /src
WORKDIR /src

RUN npm install --global "$(node -p "require('./package.json').packageManager")" \
    && pnpm install --frozen-lockfile

RUN pnpm run build

CMD ["bash"]
