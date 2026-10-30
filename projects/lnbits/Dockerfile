FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
        automake build-essential ca-certificates curl git libnss-myhostname \
        libtool pkg-config postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && pip install --no-cache-dir uv

# tools/check includes the full checkout when using a Dockerfile beside project.yaml.
COPY . /src
WORKDIR /src

# Install application, optional backend and test dependencies while online.
RUN uv sync --frozen --all-extras --group dev
RUN npm ci --no-audit --no-fund && npm run bundle
RUN npx playwright install --with-deps chromium

ENV PATH="/src/.venv/bin:$PATH" \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    LNBITS_BACKEND_WALLET_CLASS=FakeWallet

CMD ["bash"]
