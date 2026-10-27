FROM node:22-bookworm AS node

FROM golang:1.25-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git postgresql postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download
RUN cd dashboard && npm ci && npm run build
RUN cd test/integration/supabase-js && npm ci
RUN go build -gcflags=all="-N -l" -o /usr/local/bin/inz ./cmd/inz

# Local Postgres superuser so `inz dev` runs offline against INSTANCEZ_DATABASE_URL.
RUN service postgresql start \
    && su postgres -c "psql -c \"CREATE ROLE instancez LOGIN SUPERUSER PASSWORD 'instancez'\"" \
    && su postgres -c "createdb -O instancez instancez" \
    && service postgresql stop
ENV INSTANCEZ_DATABASE_URL=postgres://instancez:instancez@localhost:5432/instancez?sslmode=disable

# Warm the build cache; failures are reported, not fatal.
RUN go test -race ./... || echo "WARNING: go unit tests reported failures"
RUN go vet -tags=integration ./... || echo "WARNING: integration build reported failures"
