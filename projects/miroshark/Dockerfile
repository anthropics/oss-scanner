# MiroShark: Flask backend (Python, uv) + Vue 3 / Vite frontend, with Neo4j as the graph store.
# Mirrors the repo's own Dockerfile, then adds the dev deps, a frontend build and the offline unit suite.
# Neo4j is not in the image: the backend boots without it and graph-backed endpoints fail soft.
FROM python:3.14
ENV DEBIAN_FRONTEND=noninteractive

# Node 22 (Vite needs >=20.19/22.12; Debian's nodejs is too old).
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates gnupg git jq \
  && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Backend deps (default groups include dev, so pytest is there), root + frontend node deps, then the SPA build.
RUN cd backend && uv sync --frozen
RUN npm ci && npm ci --prefix frontend && npm run build

# The offline unit suite (the same gate CI runs), before .env exists so it matches CI. A failing test does not abort the build.
RUN cd backend && (uv run pytest -m "not integration" -q || echo "WARNING: unit tests reported failures")

# Offline config so the backend can boot with no network: placeholder keys and a fixed internal key.
RUN printf '%s\n' \
  'LLM_API_KEY=offline-placeholder' 'SMART_API_KEY=offline-placeholder' 'NER_API_KEY=offline-placeholder' \
  'OPENAI_API_KEY=offline-placeholder' 'EMBEDDING_API_KEY=offline-placeholder' \
  'MIROSHARK_INTERNAL_KEY=scan-internal-key' > /src/.env
