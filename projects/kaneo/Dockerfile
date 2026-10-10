FROM node:24.19.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    HUSKY=0 \
    NODE_OPTIONS=--no-experimental-webstorage \
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kaneo_test

RUN apt-get update && apt-get install -y --no-install-recommends postgresql \
    && rm -rf /var/lib/apt/lists/*

RUN service postgresql start \
    && su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres'\"" \
    && su postgres -c "createdb kaneo_test" \
    && service postgresql stop

RUN npm install -g pnpm@10.32.1

COPY . /src
WORKDIR /src

RUN pnpm install --frozen-lockfile

RUN pnpm --filter "@kaneo/api..." --filter "@kaneo/web..." --filter "@kaneo/mcp..." run build

RUN pnpm test || echo "WARNING: unit tests reported failures"

RUN service postgresql start \
    && (pnpm test:integration || echo "WARNING: integration tests reported failures") \
    && service postgresql stop
